use std::collections::HashSet;
use std::fs::{self, File, OpenOptions};
use std::io::{BufReader, Read};
use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
use std::path::{Component, Path, PathBuf};
use std::process::{Command, Stdio};

use attestation_verify::{
    Bundle, BundleSet, CheckpointOriginPolicy, CommitSha, GithubPolicy, RefPolicy,
    RepositoryIdentity, SignerPolicy, SourcePolicy, Subject, TrustStore, Verifier, WorkflowPath,
    WorkflowRevisionPolicy,
};
use semver::Version;
use sha2::{Digest, Sha256};
use wsh::{BundleStatus, activate_bundle, active_bundle, entrypoints, verify_bundle};

const WSH_REPOSITORY: &str = "wakamex/wsh";
const WSH_OWNER_ID: u64 = 16_990_562;
const WSH_REPOSITORY_ID: u64 = 1_354_181_503;
const WSH_SIGNER_WORKFLOW: &str = ".github/workflows/publish.yml";
const REKOR_V1_URL: &str = "https://rekor.sigstore.dev";
const REKOR_V1_ORIGIN: &str = "rekor.sigstore.dev - 1193050959916656506";
const MAX_ATTESTATION_BYTES: u64 = 4 * 1024 * 1024;
const MAX_ARCHIVE_BYTES: u64 = 512 * 1024 * 1024;
const MAX_UNPACKED_BYTES: u64 = 1024 * 1024 * 1024;
const MAX_ARCHIVE_ENTRIES: usize = 100_000;
const CURRENT_MANAGER_VERSION: &str = env!("CARGO_PKG_VERSION");

#[derive(Debug)]
pub struct InstallRequest {
    pub archive: PathBuf,
    pub attestation: PathBuf,
    pub tag: String,
    pub commit: String,
    pub install_root: PathBuf,
    pub state_root: PathBuf,
    pub allow_downgrade: bool,
}

#[derive(Debug)]
pub struct InstallResult {
    pub bundle: PathBuf,
    pub archive_sha256: String,
    pub manifest_sha256: String,
}

#[derive(Debug, Clone)]
pub struct GithubBuildIdentity<'a> {
    pub repository: &'a str,
    pub owner_id: u64,
    pub repository_id: u64,
    pub source_ref: &'a str,
    pub source_commit: &'a str,
    pub signer_workflow: &'a str,
    pub signer_commit: &'a str,
}

pub fn verify_github_build_provenance(
    artifact_sha256: &str,
    attestation_bytes: &[u8],
    identity: &GithubBuildIdentity<'_>,
) -> Result<Option<String>, String> {
    let subject = Subject::from_digest_hex(artifact_sha256)
        .map_err(|error| format!("invalid artifact digest: {error}"))?;
    let bundle = parse_single_bundle(attestation_bytes)?;
    let source_commit = CommitSha::new(identity.source_commit)
        .map_err(|error| format!("invalid source commit: {error}"))?;
    let signer_commit = CommitSha::new(identity.signer_commit)
        .map_err(|error| format!("invalid signer commit: {error}"))?;
    let source_repository = RepositoryIdentity::parse(identity.repository)
        .map_err(|error| format!("invalid source repository policy: {error}"))?
        .with_owner_id(identity.owner_id)
        .with_repository_id(identity.repository_id);
    let signer_repository = RepositoryIdentity::parse(identity.repository)
        .map_err(|error| format!("invalid signer repository policy: {error}"))?;
    let policy = GithubPolicy::builder()
        .source(SourcePolicy {
            repository: source_repository,
            git_ref: RefPolicy::Exact(identity.source_ref.to_owned()),
            commit: Some(source_commit),
        })
        .signer(SignerPolicy {
            repository: signer_repository,
            path: WorkflowPath::new(identity.signer_workflow)
                .map_err(|error| format!("invalid signer workflow policy: {error}"))?,
            revision: WorkflowRevisionPolicy::Sha(signer_commit),
        })
        .build()
        .map_err(|error| format!("invalid GitHub identity policy: {error}"))?;
    let trust_store = TrustStore::embedded_public_good()
        .map_err(|error| format!("could not load the embedded Sigstore trust root: {error}"))?;
    let rekor = trust_store
        .tlogs
        .iter()
        .find(|log| log.base_url == REKOR_V1_URL)
        .ok_or_else(|| "embedded Sigstore trust root has no supported Rekor v1 log".to_owned())?;
    let checkpoint_policy = CheckpointOriginPolicy::builder()
        .allow_origin(rekor, REKOR_V1_ORIGIN)
        .and_then(|builder| builder.build())
        .map_err(|error| format!("could not construct the Rekor checkpoint policy: {error}"))?;
    let verifier = Verifier::builder()
        .trust_store(trust_store)
        .github_policy(policy)
        .checkpoint_origin_policy(checkpoint_policy)
        .build()
        .map_err(|error| format!("could not construct the provenance verifier: {error}"))?;
    let report = verifier
        .verify_digest(&subject, &bundle)
        .map_err(|error| format!("GitHub build provenance verification failed: {error}"))?;
    Ok(report.subject.name)
}

pub fn install_release(request: &InstallRequest) -> Result<InstallResult, String> {
    validate_release_tag(&request.tag)?;
    CommitSha::new(&request.commit).map_err(|error| format!("invalid source commit: {error}"))?;
    let archive_name = regular_file_name(&request.archive, MAX_ARCHIVE_BYTES, "release archive")?;
    regular_file_name(
        &request.attestation,
        MAX_ATTESTATION_BYTES,
        "attestation bundle",
    )?;
    let archive_sha256 = sha256_file(&request.archive)?;
    let attestation_bytes = fs::read(&request.attestation).map_err(|error| {
        format!(
            "could not read attestation {}: {error}",
            request.attestation.display()
        )
    })?;
    let source_ref = format!("refs/tags/{}", request.tag);
    let subject_name = verify_github_build_provenance(
        &archive_sha256,
        &attestation_bytes,
        &GithubBuildIdentity {
            repository: WSH_REPOSITORY,
            owner_id: WSH_OWNER_ID,
            repository_id: WSH_REPOSITORY_ID,
            source_ref: &source_ref,
            source_commit: &request.commit,
            signer_workflow: WSH_SIGNER_WORKFLOW,
            signer_commit: &request.commit,
        },
    )?
    .ok_or_else(|| "build provenance subject has no artifact name".to_owned())?;
    let attested_name = Path::new(&subject_name)
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| "attested artifact name must identify a UTF-8 file".to_owned())?;
    if attested_name != archive_name {
        return Err(format!(
            "attested artifact name mismatch: expected {archive_name}, got {attested_name}"
        ));
    }

    install_authenticated_archive(request, archive_sha256)
}

fn install_authenticated_archive(
    request: &InstallRequest,
    archive_sha256: String,
) -> Result<InstallResult, String> {
    validate_release_tag(&request.tag)?;
    CommitSha::new(&request.commit).map_err(|error| format!("invalid source commit: {error}"))?;
    regular_file_name(&request.archive, MAX_ARCHIVE_BYTES, "release archive")?;
    let bundles_root = request.install_root.join("bundles");
    create_private_directory(&request.install_root)?;
    create_private_directory(&bundles_root)?;
    let mut staging = StagingDirectory::create(&bundles_root)?;
    let extracted = extract_archive(&request.archive, staging.path())?;
    let verified = verify_bundle(&extracted)?;
    if verified.manifest.status != BundleStatus::Release {
        return Err("an official install requires a release bundle".into());
    }
    if verified.manifest.release_id != request.tag {
        return Err(format!(
            "bundle release identity mismatch: expected {}, got {}",
            request.tag, verified.manifest.release_id
        ));
    }
    if !verified
        .manifest
        .rust
        .source_revision
        .eq_ignore_ascii_case(&request.commit)
    {
        return Err(format!(
            "bundle source revision mismatch: expected {}, got {}",
            request.commit, verified.manifest.rust.source_revision
        ));
    }
    require_no_implicit_downgrade(
        &request.state_root,
        &verified.manifest.release_id,
        request.allow_downgrade,
    )?;
    let expected_root_name = extracted
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| "archive bundle directory name must be UTF-8".to_owned())?;
    if expected_root_name != verified.manifest_sha256 {
        return Err(format!(
            "bundle directory identity mismatch: expected {}, got {expected_root_name}",
            verified.manifest_sha256
        ));
    }
    require_compatible_manager(&verified.manifest.minimum_manager_version)?;
    smoke_test(&extracted, &verified.manifest)?;

    let destination = bundles_root.join(&verified.manifest_sha256);
    if destination.exists() {
        let installed = verify_bundle(&destination)?;
        if installed.manifest_sha256 != verified.manifest_sha256 {
            return Err(format!(
                "installed bundle identity changed: {}",
                destination.display()
            ));
        }
    } else {
        fs::rename(&extracted, &destination).map_err(|error| {
            format!(
                "could not atomically install {} as {}: {error}",
                extracted.display(),
                destination.display()
            )
        })?;
        sync_directory(&bundles_root)?;
    }
    staging.remove()?;
    let manifest_sha256 = activate_bundle(&request.state_root, &destination)?;
    Ok(InstallResult {
        bundle: destination,
        archive_sha256,
        manifest_sha256,
    })
}

fn parse_single_bundle(bytes: &[u8]) -> Result<Bundle, String> {
    if let Ok(bundle) = Bundle::from_json(bytes) {
        return Ok(bundle);
    }
    let set = BundleSet::from_json_lines(bytes)
        .map_err(|error| format!("invalid Sigstore bundle: {error}"))?;
    let [bundle] = <[Bundle; 1]>::try_from(set.bundles).map_err(|bundles| {
        format!(
            "attestation input must contain exactly one Sigstore bundle, got {}",
            bundles.len()
        )
    })?;
    Ok(bundle)
}

fn validate_release_tag(tag: &str) -> Result<(), String> {
    let version = tag
        .strip_prefix('v')
        .ok_or_else(|| "release tag must start with v".to_owned())?;
    let parsed =
        Version::parse(version).map_err(|error| format!("invalid release tag: {error}"))?;
    if !parsed.pre.is_empty() || !parsed.build.is_empty() || format!("v{parsed}") != tag {
        return Err("release tag must be canonical vMAJOR.MINOR.PATCH".into());
    }
    Ok(())
}

fn require_compatible_manager(minimum: &str) -> Result<(), String> {
    let required = Version::parse(minimum)
        .map_err(|error| format!("invalid minimum manager version in bundle: {error}"))?;
    let current = Version::parse(CURRENT_MANAGER_VERSION)
        .map_err(|error| format!("invalid installed manager version: {error}"))?;
    if required > current {
        return Err(format!(
            "bundle requires wsh manager {required}, installed version is {current}"
        ));
    }
    Ok(())
}

fn require_no_implicit_downgrade(
    state_root: &Path,
    candidate_release: &str,
    allow_downgrade: bool,
) -> Result<(), String> {
    if allow_downgrade || !state_root.join("bundle-state.json").exists() {
        return Ok(());
    }
    let current_root = active_bundle(state_root)?;
    let current = verify_bundle(&current_root)?;
    if current.manifest.status != BundleStatus::Release {
        return Ok(());
    }
    let current_version = Version::parse(
        current
            .manifest
            .release_id
            .strip_prefix('v')
            .ok_or_else(|| "active release identity does not start with v".to_owned())?,
    )
    .map_err(|error| format!("invalid active release identity: {error}"))?;
    let candidate_version = Version::parse(
        candidate_release
            .strip_prefix('v')
            .ok_or_else(|| "candidate release identity does not start with v".to_owned())?,
    )
    .map_err(|error| format!("invalid candidate release identity: {error}"))?;
    if candidate_version < current_version {
        return Err(format!(
            "refusing downgrade from v{current_version} to v{candidate_version}; pass --allow-downgrade to request it explicitly"
        ));
    }
    Ok(())
}

fn regular_file_name(path: &Path, maximum: u64, description: &str) -> Result<String, String> {
    let metadata = fs::symlink_metadata(path).map_err(|error| {
        format!(
            "could not inspect {description} {}: {error}",
            path.display()
        )
    })?;
    if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
        return Err(format!("{description} must be a regular file"));
    }
    if metadata.len() > maximum {
        return Err(format!("{description} exceeds {maximum} bytes"));
    }
    path.file_name()
        .and_then(|name| name.to_str())
        .map(str::to_owned)
        .ok_or_else(|| format!("{description} name must be UTF-8"))
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let file =
        File::open(path).map_err(|error| format!("could not open {}: {error}", path.display()))?;
    let mut reader = BufReader::new(file);
    let mut hash = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let count = reader
            .read(&mut buffer)
            .map_err(|error| format!("could not read {}: {error}", path.display()))?;
        if count == 0 {
            break;
        }
        hash.update(&buffer[..count]);
    }
    Ok(format!("{:x}", hash.finalize()))
}

fn create_private_directory(path: &Path) -> Result<(), String> {
    fs::create_dir_all(path)
        .map_err(|error| format!("could not create {}: {error}", path.display()))?;
    let metadata = fs::symlink_metadata(path)
        .map_err(|error| format!("could not inspect {}: {error}", path.display()))?;
    if !metadata.file_type().is_dir() || metadata.file_type().is_symlink() {
        return Err(format!(
            "directory must not be a symbolic link: {}",
            path.display()
        ));
    }
    fs::set_permissions(path, fs::Permissions::from_mode(0o700))
        .map_err(|error| format!("could not secure {}: {error}", path.display()))
}

struct StagingDirectory {
    path: PathBuf,
    removed: bool,
}

impl StagingDirectory {
    fn create(parent: &Path) -> Result<Self, String> {
        for attempt in 0..100_u32 {
            let nonce = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map_err(|_| "system clock is before the Unix epoch".to_owned())?
                .as_nanos();
            let path = parent.join(format!(
                ".install.{}.{}.{attempt}",
                std::process::id(),
                nonce
            ));
            match fs::create_dir(&path) {
                Ok(()) => {
                    fs::set_permissions(&path, fs::Permissions::from_mode(0o700))
                        .map_err(|error| format!("could not secure staging directory: {error}"))?;
                    return Ok(Self {
                        path,
                        removed: false,
                    });
                }
                Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(error) => {
                    return Err(format!("could not create staging directory: {error}"));
                }
            }
        }
        Err("could not allocate a unique staging directory".into())
    }

    fn path(&self) -> &Path {
        &self.path
    }

    fn remove(&mut self) -> Result<(), String> {
        fs::remove_dir_all(&self.path).map_err(|error| {
            format!(
                "could not remove staging directory {}: {error}",
                self.path.display()
            )
        })?;
        self.removed = true;
        Ok(())
    }
}

impl Drop for StagingDirectory {
    fn drop(&mut self) {
        if !self.removed {
            let _ = fs::remove_dir_all(&self.path);
        }
    }
}

fn extract_archive(archive_path: &Path, stage: &Path) -> Result<PathBuf, String> {
    let archive_file = File::open(archive_path)
        .map_err(|error| format!("could not open {}: {error}", archive_path.display()))?;
    let decoder = xz2::read::XzDecoder::new(BufReader::new(archive_file));
    let mut archive = tar::Archive::new(decoder);
    let entries = archive
        .entries()
        .map_err(|error| format!("could not read release archive: {error}"))?;
    let mut seen = HashSet::new();
    let mut root = None;
    let mut total_size = 0_u64;

    for (index, item) in entries.enumerate() {
        if index >= MAX_ARCHIVE_ENTRIES {
            return Err(format!(
                "release archive exceeds {MAX_ARCHIVE_ENTRIES} entries"
            ));
        }
        let mut entry = item.map_err(|error| format!("invalid release archive entry: {error}"))?;
        let path = entry
            .path()
            .map_err(|error| format!("invalid release archive path: {error}"))?
            .into_owned();
        validate_archive_path(&path)?;
        if !seen.insert(path.clone()) {
            return Err(format!(
                "duplicate release archive path: {}",
                path.display()
            ));
        }
        let first = path
            .components()
            .next()
            .and_then(|component| match component {
                Component::Normal(value) => Some(PathBuf::from(value)),
                _ => None,
            })
            .ok_or_else(|| "release archive entry has no root directory".to_owned())?;
        if !is_sha256_directory(&first) {
            return Err(format!(
                "release archive root must be a SHA-256 bundle identity: {}",
                first.display()
            ));
        }
        match &root {
            Some(expected) if expected != &first => {
                return Err("release archive contains more than one bundle root".into());
            }
            None => root = Some(first),
            _ => {}
        }

        let entry_type = entry.header().entry_type();
        let destination = stage.join(&path);
        if entry_type.is_dir() {
            fs::create_dir_all(&destination).map_err(|error| {
                format!(
                    "could not create archive directory {}: {error}",
                    destination.display()
                )
            })?;
            continue;
        }
        if !entry_type.is_file() {
            return Err(format!(
                "release archive contains a non-file entry: {}",
                path.display()
            ));
        }
        let size = entry
            .header()
            .size()
            .map_err(|error| format!("invalid size for {}: {error}", path.display()))?;
        total_size = total_size
            .checked_add(size)
            .ok_or_else(|| "release archive size overflow".to_owned())?;
        if total_size > MAX_UNPACKED_BYTES {
            return Err(format!(
                "release archive exceeds {MAX_UNPACKED_BYTES} unpacked bytes"
            ));
        }
        let raw_mode = entry
            .header()
            .mode()
            .map_err(|error| format!("invalid mode for {}: {error}", path.display()))?;
        if raw_mode & 0o7000 != 0 {
            return Err(format!(
                "release archive mode contains special bits {raw_mode:o}: {}",
                path.display()
            ));
        }
        let mode = raw_mode & 0o777;
        if mode != 0o644 && mode != 0o755 {
            return Err(format!(
                "unsupported release archive mode {mode:o}: {}",
                path.display()
            ));
        }
        let parent = destination
            .parent()
            .ok_or_else(|| "archive file has no parent directory".to_owned())?;
        fs::create_dir_all(parent)
            .map_err(|error| format!("could not create {}: {error}", parent.display()))?;
        let mut output = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(mode)
            .open(&destination)
            .map_err(|error| format!("could not create {}: {error}", destination.display()))?;
        fs::set_permissions(&destination, fs::Permissions::from_mode(mode)).map_err(|error| {
            format!(
                "could not set archive mode on {}: {error}",
                destination.display()
            )
        })?;
        std::io::copy(&mut entry, &mut output)
            .map_err(|error| format!("could not extract {}: {error}", path.display()))?;
        output
            .sync_all()
            .map_err(|error| format!("could not sync {}: {error}", destination.display()))?;
    }

    let root = root.ok_or_else(|| "release archive is empty".to_owned())?;
    Ok(stage.join(root))
}

fn validate_archive_path(path: &Path) -> Result<(), String> {
    if path.as_os_str().is_empty() || path.is_absolute() {
        return Err("release archive path must be relative and non-empty".into());
    }
    for component in path.components() {
        if !matches!(component, Component::Normal(_)) {
            return Err(format!("unsafe release archive path: {}", path.display()));
        }
    }
    Ok(())
}

fn is_sha256_directory(path: &Path) -> bool {
    path.to_str().is_some_and(|value| {
        value.len() == 64
            && value
                .bytes()
                .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    })
}

fn smoke_test(root: &Path, manifest: &wsh::BundleManifest) -> Result<(), String> {
    let paths = entrypoints(root, manifest);
    let shell = Command::new(&paths.shell)
        .args(["-f", "-c", "zmodload zsh/datetime"])
        .stdout(Stdio::null())
        .status()
        .map_err(|error| format!("could not start candidate Zsh: {error}"))?;
    if !shell.success() {
        return Err(format!("candidate Zsh smoke test failed with {shell}"));
    }
    let runtime = Command::new(&paths.runtime)
        .args(["validate-theme"])
        .arg(&paths.default_theme)
        .stdout(Stdio::null())
        .status()
        .map_err(|error| format!("could not start candidate runtime: {error}"))?;
    if !runtime.success() {
        return Err(format!(
            "candidate runtime smoke test failed with {runtime}"
        ));
    }
    Ok(())
}

fn sync_directory(path: &Path) -> Result<(), String> {
    File::open(path)
        .and_then(|directory| directory.sync_all())
        .map_err(|error| format!("could not sync {}: {error}", path.display()))
}

#[cfg(test)]
mod tests {
    use super::{
        InstallRequest, install_authenticated_archive, is_sha256_directory, sha256_file,
        validate_archive_path, validate_release_tag,
    };
    use serde_json::json;
    use sha2::{Digest, Sha256};
    use std::fs::{self, File};
    use std::io::Write;
    use std::os::unix::fs::PermissionsExt;
    use std::path::{Path, PathBuf};
    use wsh::{active_bundle, rollback_bundle, verify_bundle};

    const COMMIT_A: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const COMMIT_B: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

    struct TestDirectory(PathBuf);

    impl TestDirectory {
        fn create() -> Result<Self, Box<dyn std::error::Error>> {
            for attempt in 0..100_u32 {
                let path = std::env::temp_dir().join(format!(
                    "wsh-install-test.{}.{}.{attempt}",
                    std::process::id(),
                    std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)?
                        .as_nanos()
                ));
                match fs::create_dir(&path) {
                    Ok(()) => return Ok(Self(path)),
                    Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
                    Err(error) => return Err(error.into()),
                }
            }
            Err("could not create test directory".into())
        }

        fn path(&self) -> &Path {
            &self.0
        }
    }

    impl Drop for TestDirectory {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn release_tags_are_canonical() {
        assert!(validate_release_tag("v1.2.3").is_ok());
        assert!(validate_release_tag("1.2.3").is_err());
        assert!(validate_release_tag("v1.2.3-alpha").is_err());
        assert!(validate_release_tag("v01.2.3").is_err());
    }

    #[test]
    fn archive_paths_are_relative_normal_paths() {
        assert!(validate_archive_path(Path::new("abc/manifest.json")).is_ok());
        assert!(validate_archive_path(Path::new("../escape")).is_err());
        assert!(validate_archive_path(Path::new("/absolute")).is_err());
    }

    #[test]
    fn bundle_roots_are_lowercase_sha256() {
        assert!(is_sha256_directory(Path::new(&"a".repeat(64))));
        assert!(!is_sha256_directory(Path::new(&"A".repeat(64))));
        assert!(!is_sha256_directory(Path::new("abc")));
    }

    #[test]
    fn authenticated_archive_is_atomic_and_rollback_stays_offline()
    -> Result<(), Box<dyn std::error::Error>> {
        let temporary = TestDirectory::create()?;
        let first_archive = make_release_archive(temporary.path(), "v1.2.3", COMMIT_A)?;
        let install_root = temporary.path().join("install");
        let state_root = temporary.path().join("state");
        let first_request = request(
            &first_archive,
            "v1.2.3",
            COMMIT_A,
            &install_root,
            &state_root,
            false,
        );
        let first = install_authenticated_archive(&first_request, sha256_file(&first_archive)?)?;
        assert_eq!(active_bundle(&state_root)?, first.bundle);
        assert_eq!(verify_bundle(&first.bundle)?.manifest.release_id, "v1.2.3");
        assert!(staging_directories(&install_root)?.is_empty());

        let older_archive = make_release_archive(temporary.path(), "v1.2.2", COMMIT_B)?;
        let older_request = request(
            &older_archive,
            "v1.2.2",
            COMMIT_B,
            &install_root,
            &state_root,
            false,
        );
        let error = install_authenticated_archive(&older_request, sha256_file(&older_archive)?)
            .expect_err("an implicit downgrade must be rejected");
        assert!(error.contains("refusing downgrade"));
        assert_eq!(active_bundle(&state_root)?, first.bundle);
        assert!(staging_directories(&install_root)?.is_empty());

        let explicit_request = request(
            &older_archive,
            "v1.2.2",
            COMMIT_B,
            &install_root,
            &state_root,
            true,
        );
        let older = install_authenticated_archive(&explicit_request, sha256_file(&older_archive)?)?;
        assert_eq!(active_bundle(&state_root)?, older.bundle);
        assert_eq!(rollback_bundle(&state_root)?, first.manifest_sha256);
        assert_eq!(active_bundle(&state_root)?, first.bundle);
        Ok(())
    }

    #[test]
    fn unsafe_archive_does_not_change_activation() -> Result<(), Box<dyn std::error::Error>> {
        let temporary = TestDirectory::create()?;
        let first_archive = make_release_archive(temporary.path(), "v1.2.3", COMMIT_A)?;
        let install_root = temporary.path().join("install");
        let state_root = temporary.path().join("state");
        let first_request = request(
            &first_archive,
            "v1.2.3",
            COMMIT_A,
            &install_root,
            &state_root,
            false,
        );
        let first = install_authenticated_archive(&first_request, sha256_file(&first_archive)?)?;

        let unsafe_archive = make_link_archive(temporary.path())?;
        let unsafe_request = request(
            &unsafe_archive,
            "v1.2.4",
            COMMIT_B,
            &install_root,
            &state_root,
            false,
        );
        let error = install_authenticated_archive(&unsafe_request, sha256_file(&unsafe_archive)?)
            .expect_err("a link entry must be rejected");
        assert!(error.contains("non-file entry"));
        assert_eq!(active_bundle(&state_root)?, first.bundle);
        assert!(staging_directories(&install_root)?.is_empty());
        Ok(())
    }

    #[test]
    fn candidate_contract_rejects_mismatches_before_activation()
    -> Result<(), Box<dyn std::error::Error>> {
        let temporary = TestDirectory::create()?;
        let base = FixtureOptions::release("v1.2.3", COMMIT_A);
        let cases = [
            (
                "development",
                FixtureOptions {
                    status: "development",
                    ..base
                },
                COMMIT_A,
                "requires a release bundle",
            ),
            (
                "release-id",
                FixtureOptions {
                    release_id: "v1.2.4",
                    ..base
                },
                COMMIT_A,
                "release identity mismatch",
            ),
            (
                "source-revision",
                FixtureOptions {
                    commit: COMMIT_B,
                    ..base
                },
                COMMIT_A,
                "source revision mismatch",
            ),
            (
                "manager-version",
                FixtureOptions {
                    minimum_manager_version: "999.0.0",
                    ..base
                },
                COMMIT_A,
                "requires wsh manager",
            ),
            (
                "runtime-smoke",
                FixtureOptions {
                    runtime_exit: 1,
                    ..base
                },
                COMMIT_A,
                "runtime smoke test failed",
            ),
            (
                "unlisted-file",
                FixtureOptions {
                    add_unlisted_file: true,
                    ..base
                },
                COMMIT_A,
                "unlisted",
            ),
        ];

        for (label, options, requested_commit, expected_error) in cases {
            let case_root = temporary.path().join(label);
            fs::create_dir(&case_root)?;
            let archive = make_archive(&case_root, options)?;
            let install_root = case_root.join("install");
            let state_root = case_root.join("state");
            let request = request(
                &archive,
                "v1.2.3",
                requested_commit,
                &install_root,
                &state_root,
                false,
            );
            let result = install_authenticated_archive(&request, sha256_file(&archive)?);
            let error = result.expect_err("candidate mismatch must reject installation");
            assert!(
                error.contains(expected_error),
                "{label}: expected {expected_error:?} in {error:?}"
            );
            assert!(
                !state_root.exists(),
                "{label}: activation state was created"
            );
            assert!(
                staging_directories(&install_root)?.is_empty(),
                "{label}: staging directory survived rejection"
            );
        }
        Ok(())
    }

    #[test]
    fn invalid_provenance_does_not_create_install_state() -> Result<(), Box<dyn std::error::Error>>
    {
        let temporary = TestDirectory::create()?;
        let archive = make_release_archive(temporary.path(), "v1.2.3", COMMIT_A)?;
        let attestation = temporary.path().join("invalid.sigstore.json");
        fs::write(&attestation, b"{}")?;
        let install_root = temporary.path().join("install");
        let state_root = temporary.path().join("state");
        let request = InstallRequest {
            archive,
            attestation,
            tag: "v1.2.3".to_owned(),
            commit: COMMIT_A.to_owned(),
            install_root: install_root.clone(),
            state_root: state_root.clone(),
            allow_downgrade: false,
        };
        let error = super::install_release(&request)
            .expect_err("invalid provenance must reject the candidate before extraction");
        assert!(error.contains("invalid Sigstore bundle"));
        assert!(!install_root.exists());
        assert!(!state_root.exists());
        Ok(())
    }

    fn request(
        archive: &Path,
        tag: &str,
        commit: &str,
        install_root: &Path,
        state_root: &Path,
        allow_downgrade: bool,
    ) -> InstallRequest {
        InstallRequest {
            archive: archive.to_path_buf(),
            attestation: PathBuf::from("unused-in-transaction-test"),
            tag: tag.to_owned(),
            commit: commit.to_owned(),
            install_root: install_root.to_path_buf(),
            state_root: state_root.to_path_buf(),
            allow_downgrade,
        }
    }

    fn staging_directories(install_root: &Path) -> Result<Vec<PathBuf>, std::io::Error> {
        let bundles = install_root.join("bundles");
        fs::read_dir(bundles)?
            .filter_map(|item| match item {
                Ok(item) if item.file_name().to_string_lossy().starts_with(".install.") => {
                    Some(Ok(item.path()))
                }
                Ok(_) => None,
                Err(error) => Some(Err(error)),
            })
            .collect()
    }

    #[derive(Clone, Copy)]
    struct FixtureOptions<'a> {
        tag: &'a str,
        status: &'a str,
        release_id: &'a str,
        commit: &'a str,
        minimum_manager_version: &'a str,
        runtime_exit: u8,
        add_unlisted_file: bool,
    }

    impl<'a> FixtureOptions<'a> {
        fn release(tag: &'a str, commit: &'a str) -> Self {
            Self {
                tag,
                status: "release",
                release_id: tag,
                commit,
                minimum_manager_version: "0.1.0",
                runtime_exit: 0,
                add_unlisted_file: false,
            }
        }
    }

    fn make_release_archive(
        parent: &Path,
        tag: &str,
        commit: &str,
    ) -> Result<PathBuf, Box<dyn std::error::Error>> {
        make_archive(parent, FixtureOptions::release(tag, commit))
    }

    fn make_archive(
        parent: &Path,
        options: FixtureOptions<'_>,
    ) -> Result<PathBuf, Box<dyn std::error::Error>> {
        let tag = options.tag;
        let stage = parent.join(format!("payload-{tag}"));
        fs::create_dir_all(stage.join("bin"))?;
        fs::create_dir_all(stage.join("share/wsh/zdotdir"))?;
        fs::create_dir_all(stage.join("share/wsh/themes"))?;
        fs::copy("/bin/zsh", stage.join("bin/zsh"))?;
        write_file(
            &stage.join("bin/wsh-runtime"),
            format!("#!/bin/sh\nexit {}\n", options.runtime_exit).as_bytes(),
            0o755,
        )?;
        write_file(
            &stage.join("share/wsh/integration.zsh"),
            b"# transaction fixture\n",
            0o644,
        )?;
        write_file(
            &stage.join("share/wsh/zdotdir/.zshenv"),
            b"# transaction fixture\n",
            0o644,
        )?;
        write_file(
            &stage.join("share/wsh/themes/minimal.toml"),
            b"schema_version = 1\n",
            0o644,
        )?;
        fs::set_permissions(stage.join("bin/zsh"), fs::Permissions::from_mode(0o755))?;

        let mut files = collect_file_records(&stage)?;
        files.sort_by(|left, right| left["path"].as_str().cmp(&right["path"].as_str()));
        if options.add_unlisted_file {
            write_file(
                &stage.join("share/wsh/unlisted"),
                b"not in manifest\n",
                0o644,
            )?;
        }
        let manifest = json!({
            "schema_version": 1,
            "status": options.status,
            "release_id": options.release_id,
            "target": "x86_64-unknown-linux-gnu",
            "minimum_manager_version": options.minimum_manager_version,
            "builder": {
                "base_image": null,
                "package_lock_sha256": null,
                "rust_toolchain_sha256": null,
                "source_date_epoch": 1,
                "environment": {"lang": "C", "lc_all": "C", "tz": "UTC", "build_jobs": "1"}
            },
            "zsh": {
                "version": "fixture",
                "source_archive": "fixture",
                "source_sha256": "fixture",
                "signer_fingerprint": "fixture",
                "source_revision": "fixture",
                "patches": [],
                "configure_args": [],
                "compiler": "fixture",
                "linker": "fixture"
            },
            "rust": {
                "source_revision": options.commit,
                "lockfile_sha256": "fixture",
                "target": "x86_64-unknown-linux-gnu",
                "compiler": "fixture",
                "profile": "release"
            },
            "api_versions": {"runtime_protocol": 1, "provider_schema": 1, "theme_schema": 1, "integration_api": 1},
            "entrypoints": {
                "shell": "bin/zsh",
                "runtime": "bin/wsh-runtime",
                "integration": "share/wsh/integration.zsh",
                "default_theme": "share/wsh/themes/minimal.toml"
            },
            "requirements": {"dynamic_libraries": [], "minimum_glibc": null},
            "files": files
        });
        let manifest_bytes = serde_json::to_vec(&manifest)?;
        fs::write(stage.join("manifest.json"), &manifest_bytes)?;
        fs::set_permissions(
            stage.join("manifest.json"),
            fs::Permissions::from_mode(0o644),
        )?;
        let identity = format!("{:x}", Sha256::digest(&manifest_bytes));
        let bundle = parent.join(&identity);
        fs::rename(&stage, &bundle)?;

        let archive_path = parent.join(format!("wsh-{tag}-x86_64-unknown-linux-gnu.tar.xz"));
        let file = File::create(&archive_path)?;
        let encoder = xz2::write::XzEncoder::new(file, 6);
        let mut archive = tar::Builder::new(encoder);
        archive.append_dir_all(&identity, &bundle)?;
        let encoder = archive.into_inner()?;
        encoder.finish()?;
        fs::remove_dir_all(bundle)?;
        Ok(archive_path)
    }

    fn make_link_archive(parent: &Path) -> Result<PathBuf, Box<dyn std::error::Error>> {
        let path = parent.join("unsafe.tar.xz");
        let file = File::create(&path)?;
        let encoder = xz2::write::XzEncoder::new(file, 6);
        let mut archive = tar::Builder::new(encoder);
        let mut header = tar::Header::new_gnu();
        header.set_entry_type(tar::EntryType::Symlink);
        header.set_size(0);
        header.set_mode(0o777);
        header.set_link_name("../escape")?;
        header.set_cksum();
        archive.append_data(&mut header, format!("{}/link", "c".repeat(64)), &[][..])?;
        let encoder = archive.into_inner()?;
        encoder.finish()?;
        Ok(path)
    }

    fn write_file(path: &Path, bytes: &[u8], mode: u32) -> Result<(), std::io::Error> {
        let mut file = File::create(path)?;
        file.write_all(bytes)?;
        file.sync_all()?;
        fs::set_permissions(path, fs::Permissions::from_mode(mode))
    }

    fn collect_file_records(
        root: &Path,
    ) -> Result<Vec<serde_json::Value>, Box<dyn std::error::Error>> {
        let mut records = Vec::new();
        let mut pending = vec![root.to_path_buf()];
        while let Some(directory) = pending.pop() {
            for item in fs::read_dir(directory)? {
                let path = item?.path();
                let metadata = fs::symlink_metadata(&path)?;
                if metadata.file_type().is_dir() {
                    pending.push(path);
                } else if metadata.file_type().is_file() {
                    let bytes = fs::read(&path)?;
                    records.push(json!({
                        "path": path.strip_prefix(root)?.to_str().ok_or("non-UTF-8 fixture path")?,
                        "kind": "file",
                        "mode": metadata.permissions().mode() & 0o777,
                        "size": bytes.len(),
                        "sha256": format!("{:x}", Sha256::digest(&bytes))
                    }));
                }
            }
        }
        Ok(records)
    }
}
