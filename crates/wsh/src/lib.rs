use std::collections::HashSet;
use std::fs::{self, File};
use std::io::{BufReader, Read};
use std::os::unix::fs::MetadataExt;
use std::path::{Component, Path, PathBuf};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

const MANIFEST_NAME: &str = "manifest.json";
const MAX_MANIFEST_BYTES: u64 = 1024 * 1024;
const MAX_STATE_BYTES: u64 = 16 * 1024;
const STATE_FILE_NAME: &str = "bundle-state.json";
const STATE_VERSION: u32 = 2;
const ZDOTDIR_PATH: &str = "share/wsh/zdotdir";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BundleManifest {
    pub schema_version: u32,
    pub status: BundleStatus,
    pub release_id: String,
    pub target: String,
    pub minimum_manager_version: String,
    pub builder: Builder,
    pub zsh: ZshBuild,
    pub rust: RustBuild,
    pub api_versions: ApiVersions,
    pub entrypoints: Entrypoints,
    pub requirements: Requirements,
    pub files: Vec<PayloadFile>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Builder {
    pub base_image: Option<String>,
    pub package_lock_sha256: Option<String>,
    pub rust_toolchain_sha256: Option<String>,
    pub source_date_epoch: Option<u64>,
    pub environment: BuildEnvironment,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BuildEnvironment {
    pub lang: String,
    pub lc_all: String,
    pub tz: String,
    pub build_jobs: String,
}

#[derive(Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum BundleStatus {
    Development,
    Release,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ZshBuild {
    pub version: String,
    pub source_mode: Option<String>,
    pub source_repository: Option<String>,
    pub source_archive: String,
    pub source_sha256: String,
    pub signer_fingerprint: Option<String>,
    pub source_revision: String,
    pub source_tree: Option<String>,
    pub patches: Vec<String>,
    pub configure_args: Vec<String>,
    pub compiler: String,
    pub linker: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RustBuild {
    pub source_revision: String,
    pub lockfile_sha256: String,
    pub target: String,
    pub compiler: String,
    pub profile: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApiVersions {
    pub runtime_protocol: u32,
    pub provider_schema: u32,
    pub theme_schema: u32,
    pub integration_api: u32,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Entrypoints {
    pub shell: String,
    pub runtime: String,
    pub integration: String,
    pub default_theme: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Requirements {
    pub dynamic_libraries: Vec<String>,
    pub minimum_glibc: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PayloadFile {
    pub path: String,
    pub kind: PayloadKind,
    pub mode: u32,
    pub size: u64,
    pub sha256: String,
}

#[derive(Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum PayloadKind {
    File,
}

pub struct VerifiedBundle {
    pub manifest: BundleManifest,
    pub manifest_sha256: String,
}

pub struct EntrypointPaths {
    pub shell: PathBuf,
    pub runtime: PathBuf,
    pub integration: PathBuf,
    pub default_theme: PathBuf,
    pub zdotdir: PathBuf,
}

pub struct LaunchBundle {
    pub root: PathBuf,
    pub entrypoints: EntrypointPaths,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(deny_unknown_fields)]
struct BundleState {
    version: u32,
    active: BundleReference,
    previous: Option<BundleReference>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(deny_unknown_fields)]
struct BundleReference {
    path: PathBuf,
    manifest_sha256: String,
    launch: LaunchReference,
}

#[derive(Debug, Deserialize, Serialize, Clone, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
struct LaunchReference {
    shell: LaunchFileReference,
    runtime: LaunchFileReference,
    integration: LaunchFileReference,
    default_theme: LaunchFileReference,
    zdotdir: String,
}

#[derive(Debug, Deserialize, Serialize, Clone, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
struct LaunchFileReference {
    path: String,
    mode: u32,
    size: u64,
}

pub fn activate_bundle(state_root: &Path, bundle: &Path) -> Result<String, String> {
    let reference = verified_reference(bundle)?;
    let previous = read_state(state_root)?.map(|state| state.active);
    write_state(
        state_root,
        &BundleState {
            version: STATE_VERSION,
            active: reference.clone(),
            previous,
        },
    )?;
    Ok(reference.manifest_sha256)
}

pub fn rollback_bundle(state_root: &Path) -> Result<String, String> {
    let state = read_state(state_root)?.ok_or_else(|| "no active bundle state".to_owned())?;
    let previous = state
        .previous
        .clone()
        .ok_or_else(|| "no previous bundle to roll back to".to_owned())?;
    verify_reference(&previous)?;
    write_state(
        state_root,
        &BundleState {
            version: STATE_VERSION,
            active: previous.clone(),
            previous: Some(state.active),
        },
    )?;
    Ok(previous.manifest_sha256)
}

pub fn active_bundle(state_root: &Path) -> Result<PathBuf, String> {
    active_verified_bundle(state_root).map(|(path, _)| path)
}

pub fn active_verified_bundle(state_root: &Path) -> Result<(PathBuf, VerifiedBundle), String> {
    let state = read_state(state_root)?.ok_or_else(|| "no active bundle state".to_owned())?;
    let verified = verify_reference(&state.active)?;
    Ok((state.active.path, verified))
}

pub fn active_bundle_for_launch(state_root: &Path) -> Result<LaunchBundle, String> {
    let state = read_state(state_root)?.ok_or_else(|| "no active bundle state".to_owned())?;
    let entrypoints = resolve_launch_reference(&state.active)?;
    Ok(LaunchBundle {
        root: state.active.path,
        entrypoints,
    })
}

pub fn verify_bundle(root: &Path) -> Result<VerifiedBundle, String> {
    let (manifest, manifest_sha256) = read_manifest(root)?;

    let mut listed = HashSet::with_capacity(manifest.files.len());
    for expected in &manifest.files {
        validate_relative_path(&expected.path)?;
        if expected.path == MANIFEST_NAME {
            return Err("manifest.json must not list itself".into());
        }
        if !listed.insert(expected.path.clone()) {
            return Err(format!("duplicate payload path: {}", expected.path));
        }
        verify_payload_file(root, expected)?;
    }

    let actual = collect_payload_files(root)?;
    if actual != listed {
        let unlisted: Vec<_> = actual.difference(&listed).cloned().collect();
        let missing: Vec<_> = listed.difference(&actual).cloned().collect();
        return Err(format!(
            "payload file set mismatch; unlisted={unlisted:?}, missing={missing:?}"
        ));
    }

    for path in manifest_entrypoints(&manifest) {
        if !listed.contains(path) {
            return Err(format!(
                "entrypoint is not listed as a payload file: {path}"
            ));
        }
    }

    Ok(VerifiedBundle {
        manifest,
        manifest_sha256,
    })
}

fn read_manifest(root: &Path) -> Result<(BundleManifest, String), String> {
    let root_metadata = fs::symlink_metadata(root)
        .map_err(|error| format!("could not inspect bundle {}: {error}", root.display()))?;
    if !root_metadata.file_type().is_dir() || root_metadata.file_type().is_symlink() {
        return Err("bundle root must be a real directory".into());
    }

    let manifest_path = root.join(MANIFEST_NAME);
    let manifest_metadata = fs::symlink_metadata(&manifest_path)
        .map_err(|error| format!("could not inspect {}: {error}", manifest_path.display()))?;
    if !manifest_metadata.file_type().is_file() || manifest_metadata.file_type().is_symlink() {
        return Err("manifest.json must be a regular file".into());
    }
    if manifest_metadata.len() > MAX_MANIFEST_BYTES {
        return Err(format!("manifest.json exceeds {MAX_MANIFEST_BYTES} bytes"));
    }

    let manifest_bytes = fs::read(&manifest_path)
        .map_err(|error| format!("could not read {}: {error}", manifest_path.display()))?;
    let manifest: BundleManifest = serde_json::from_slice(&manifest_bytes)
        .map_err(|error| format!("invalid manifest.json: {error}"))?;
    validate_manifest(&manifest)?;
    let manifest_sha256 = sha256_bytes(&manifest_bytes);
    Ok((manifest, manifest_sha256))
}

pub fn entrypoints(root: &Path, manifest: &BundleManifest) -> EntrypointPaths {
    EntrypointPaths {
        shell: root.join(&manifest.entrypoints.shell),
        runtime: root.join(&manifest.entrypoints.runtime),
        integration: root.join(&manifest.entrypoints.integration),
        default_theme: root.join(&manifest.entrypoints.default_theme),
        zdotdir: root.join(ZDOTDIR_PATH),
    }
}

fn verified_reference(bundle: &Path) -> Result<BundleReference, String> {
    let path = bundle
        .canonicalize()
        .map_err(|error| format!("could not resolve bundle {}: {error}", bundle.display()))?;
    let verified = verify_bundle(&path)?;
    let launch = launch_reference(&verified.manifest)?;
    Ok(BundleReference {
        path,
        manifest_sha256: verified.manifest_sha256,
        launch,
    })
}

fn verify_reference(reference: &BundleReference) -> Result<VerifiedBundle, String> {
    let verified = verify_bundle(&reference.path)?;
    if verified.manifest_sha256 != reference.manifest_sha256 {
        return Err(format!(
            "active bundle manifest digest changed: {}",
            reference.path.display()
        ));
    }
    if launch_reference(&verified.manifest)? != reference.launch {
        return Err(format!(
            "bundle launch record changed: {}",
            reference.path.display()
        ));
    }
    Ok(verified)
}

fn read_state(state_root: &Path) -> Result<Option<BundleState>, String> {
    let path = state_root.join(STATE_FILE_NAME);
    let metadata = match fs::symlink_metadata(&path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(format!("could not inspect {}: {error}", path.display())),
    };
    if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
        return Err("bundle state must be a regular file".into());
    }
    if metadata.len() > MAX_STATE_BYTES {
        return Err("bundle state is too large".into());
    }
    let bytes =
        fs::read(&path).map_err(|error| format!("could not read {}: {error}", path.display()))?;
    let state: BundleState =
        serde_json::from_slice(&bytes).map_err(|error| format!("invalid bundle state: {error}"))?;
    if state.version != STATE_VERSION {
        return Err(format!(
            "unsupported bundle state version: {}",
            state.version
        ));
    }
    Ok(Some(state))
}

fn write_state(state_root: &Path, state: &BundleState) -> Result<(), String> {
    use std::io::Write as _;
    use std::os::unix::fs::{OpenOptionsExt as _, PermissionsExt as _};

    let mut encoded = serde_json::to_vec(state)
        .map_err(|error| format!("could not encode bundle state: {error}"))?;
    encoded.push(b'\n');
    if encoded.len() > MAX_STATE_BYTES as usize {
        return Err("bundle state is too large".into());
    }

    fs::create_dir_all(state_root).map_err(|error| {
        format!(
            "could not create state directory {}: {error}",
            state_root.display()
        )
    })?;
    let root_metadata = fs::symlink_metadata(state_root).map_err(|error| {
        format!(
            "could not inspect state directory {}: {error}",
            state_root.display()
        )
    })?;
    if !root_metadata.file_type().is_dir() || root_metadata.file_type().is_symlink() {
        return Err("state root must be a real directory".into());
    }
    fs::set_permissions(state_root, fs::Permissions::from_mode(0o700)).map_err(|error| {
        format!(
            "could not secure state directory {}: {error}",
            state_root.display()
        )
    })?;
    let destination = state_root.join(STATE_FILE_NAME);
    let nonce = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_err(|_| "system clock is before the Unix epoch")?
        .as_nanos();
    let temporary = state_root.join(format!(
        ".{STATE_FILE_NAME}.{}.{nonce}.tmp",
        std::process::id()
    ));
    let result = (|| {
        let mut file = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&temporary)
            .map_err(|error| format!("could not create {}: {error}", temporary.display()))?;
        file.write_all(&encoded)
            .map_err(|error| format!("could not write bundle state: {error}"))?;
        file.sync_all()
            .map_err(|error| format!("could not sync bundle state: {error}"))?;
        fs::rename(&temporary, &destination).map_err(|error| {
            format!(
                "could not replace bundle state {}: {error}",
                destination.display()
            )
        })?;
        File::open(state_root)
            .and_then(|directory| directory.sync_all())
            .map_err(|error| format!("could not sync {}: {error}", state_root.display()))
    })();
    if result.is_err() {
        let _ = fs::remove_file(&temporary);
    }
    result
}

fn validate_manifest(manifest: &BundleManifest) -> Result<(), String> {
    if manifest.schema_version != 1 {
        return Err(format!(
            "unsupported manifest schema version: {}",
            manifest.schema_version
        ));
    }
    if manifest.target != "x86_64-unknown-linux-gnu" {
        return Err(format!("unsupported bundle target: {}", manifest.target));
    }
    if manifest.release_id.is_empty() || manifest.minimum_manager_version.is_empty() {
        return Err("release_id and minimum_manager_version must not be empty".into());
    }
    for version in [
        manifest.api_versions.runtime_protocol,
        manifest.api_versions.provider_schema,
        manifest.api_versions.theme_schema,
        manifest.api_versions.integration_api,
    ] {
        if version != 1 {
            return Err(format!("unsupported API version: {version}"));
        }
    }
    for path in [
        &manifest.entrypoints.shell,
        &manifest.entrypoints.runtime,
        &manifest.entrypoints.integration,
        &manifest.entrypoints.default_theme,
    ] {
        validate_relative_path(path)?;
    }
    if manifest.files.is_empty() {
        return Err("manifest contains no payload files".into());
    }
    Ok(())
}

fn manifest_entrypoints(manifest: &BundleManifest) -> [&str; 4] {
    [
        &manifest.entrypoints.shell,
        &manifest.entrypoints.runtime,
        &manifest.entrypoints.integration,
        &manifest.entrypoints.default_theme,
    ]
}

fn launch_reference(manifest: &BundleManifest) -> Result<LaunchReference, String> {
    let file = |path: &str| -> Result<LaunchFileReference, String> {
        let expected = manifest
            .files
            .iter()
            .find(|file| file.path == path)
            .ok_or_else(|| format!("entrypoint is not listed as a payload file: {path}"))?;
        Ok(LaunchFileReference {
            path: expected.path.clone(),
            mode: expected.mode,
            size: expected.size,
        })
    };
    Ok(LaunchReference {
        shell: file(&manifest.entrypoints.shell)?,
        runtime: file(&manifest.entrypoints.runtime)?,
        integration: file(&manifest.entrypoints.integration)?,
        default_theme: file(&manifest.entrypoints.default_theme)?,
        zdotdir: ZDOTDIR_PATH.into(),
    })
}

fn resolve_launch_reference(reference: &BundleReference) -> Result<EntrypointPaths, String> {
    let root_metadata = fs::symlink_metadata(&reference.path).map_err(|error| {
        format!(
            "could not inspect bundle {}: {error}",
            reference.path.display()
        )
    })?;
    if !root_metadata.file_type().is_dir() || root_metadata.file_type().is_symlink() {
        return Err("bundle root must be a real directory".into());
    }
    let zdotdir = reference.path.join(&reference.launch.zdotdir);
    validate_relative_path(&reference.launch.zdotdir)?;
    let zdotdir_metadata = fs::symlink_metadata(&zdotdir)
        .map_err(|error| format!("could not inspect {}: {error}", zdotdir.display()))?;
    if !zdotdir_metadata.file_type().is_dir() || zdotdir_metadata.file_type().is_symlink() {
        return Err("ZDOTDIR must be a real directory".into());
    }
    Ok(EntrypointPaths {
        shell: resolve_launch_file(&reference.path, &reference.launch.shell)?,
        runtime: resolve_launch_file(&reference.path, &reference.launch.runtime)?,
        integration: resolve_launch_file(&reference.path, &reference.launch.integration)?,
        default_theme: resolve_launch_file(&reference.path, &reference.launch.default_theme)?,
        zdotdir,
    })
}

fn resolve_launch_file(root: &Path, expected: &LaunchFileReference) -> Result<PathBuf, String> {
    validate_relative_path(&expected.path)?;
    verify_file_metadata(root, &expected.path, expected.mode, expected.size)
}

fn validate_relative_path(path: &str) -> Result<(), String> {
    if path.is_empty() || path.contains('\\') {
        return Err(format!("invalid payload path: {path:?}"));
    }
    let candidate = Path::new(path);
    if candidate.is_absolute()
        || candidate
            .components()
            .any(|component| !matches!(component, Component::Normal(_)))
    {
        return Err(format!(
            "payload path is not normalized and relative: {path}"
        ));
    }
    Ok(())
}

fn verify_payload_file(root: &Path, expected: &PayloadFile) -> Result<(), String> {
    let path = verify_payload_metadata(root, expected)?;
    let actual_digest = sha256_file(&path)?;
    if actual_digest != expected.sha256 {
        return Err(format!("digest mismatch for {}", expected.path));
    }
    Ok(())
}

fn verify_payload_metadata(root: &Path, expected: &PayloadFile) -> Result<PathBuf, String> {
    if expected.kind != PayloadKind::File {
        return Err(format!("unsupported payload type for {}", expected.path));
    }
    if expected.mode > 0o7777 {
        return Err(format!("invalid mode for {}", expected.path));
    }
    if expected.sha256.len() != 64
        || !expected
            .sha256
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err(format!("invalid SHA-256 digest for {}", expected.path));
    }

    verify_file_metadata(root, &expected.path, expected.mode, expected.size)
}

fn verify_file_metadata(
    root: &Path,
    relative: &str,
    expected_mode: u32,
    expected_size: u64,
) -> Result<PathBuf, String> {
    let path = root.join(relative);
    let metadata = fs::symlink_metadata(&path)
        .map_err(|error| format!("could not inspect {relative}: {error}"))?;
    if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
        return Err(format!("payload is not a regular file: {relative}"));
    }
    if metadata.len() != expected_size {
        return Err(format!("size mismatch for {relative}"));
    }
    if metadata.mode() & 0o7777 != expected_mode {
        return Err(format!("mode mismatch for {relative}"));
    }
    Ok(path)
}

fn collect_payload_files(root: &Path) -> Result<HashSet<String>, String> {
    let mut found = HashSet::new();
    let mut directories = vec![root.to_path_buf()];
    while let Some(directory) = directories.pop() {
        for entry in fs::read_dir(&directory)
            .map_err(|error| format!("could not read {}: {error}", directory.display()))?
        {
            let entry = entry.map_err(|error| format!("could not read bundle entry: {error}"))?;
            let path = entry.path();
            let metadata = fs::symlink_metadata(&path)
                .map_err(|error| format!("could not inspect {}: {error}", path.display()))?;
            let relative = path
                .strip_prefix(root)
                .map_err(|error| format!("invalid bundle path: {error}"))?;
            let relative = relative
                .to_str()
                .ok_or_else(|| format!("bundle path is not UTF-8: {}", relative.display()))?;
            if metadata.file_type().is_symlink() {
                return Err(format!("symbolic links are not allowed: {relative}"));
            } else if metadata.file_type().is_dir() {
                directories.push(path);
            } else if metadata.file_type().is_file() {
                if relative != MANIFEST_NAME {
                    found.insert(relative.to_owned());
                }
            } else {
                return Err(format!("special files are not allowed: {relative}"));
            }
        }
    }
    Ok(found)
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let file =
        File::open(path).map_err(|error| format!("could not open {}: {error}", path.display()))?;
    let mut reader = BufReader::new(file);
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; 64 * 1024];
    loop {
        let count = reader
            .read(&mut buffer)
            .map_err(|error| format!("could not read {}: {error}", path.display()))?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn sha256_bytes(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::{PermissionsExt, symlink};

    fn write_test_bundle(root: &Path) {
        let paths = [
            ("bin/zsh", b"shell".as_slice(), 0o755),
            ("bin/wsh-runtime", b"runtime".as_slice(), 0o755),
            (
                "share/wsh/integration.zsh",
                b"integration".as_slice(),
                0o644,
            ),
            (
                "share/wsh/zdotdir/.zshenv",
                b"environment".as_slice(),
                0o644,
            ),
            ("share/wsh/zdotdir/.zshrc", b"startup".as_slice(), 0o644),
            ("share/wsh/themes/minimal.toml", b"theme".as_slice(), 0o644),
        ];
        let mut files = Vec::new();
        for (path, bytes, mode) in paths {
            let destination = root.join(path);
            fs::create_dir_all(destination.parent().unwrap()).unwrap();
            fs::write(&destination, bytes).unwrap();
            fs::set_permissions(&destination, fs::Permissions::from_mode(mode)).unwrap();
            files.push(serde_json::json!({
                "path": path,
                "kind": "file",
                "mode": mode,
                "size": bytes.len(),
                "sha256": sha256_bytes(bytes)
            }));
        }
        let manifest = serde_json::json!({
            "schema_version": 1,
            "status": "development",
            "release_id": "test",
            "target": "x86_64-unknown-linux-gnu",
            "minimum_manager_version": "0.1.0",
            "builder": {
                "base_image": null,
                "package_lock_sha256": null,
                "rust_toolchain_sha256": null,
                "source_date_epoch": null,
                "environment": {"lang":"C","lc_all":"C","tz":"UTC","build_jobs":"1"}
            },
            "zsh": {
                "version": "5.9.2",
                "source_archive": "zsh-5.9.2.tar.xz",
                "source_sha256": "36fa734374b44783582cec09bcd67822e2f992c779ec1624ab5596df078d2f81",
                "signer_fingerprint": "7CA7ECAAF06216B90F894146ACF8146CAE8CBBC4",
                "source_revision": "zsh-5.9.2",
                "patches": [],
                "configure_args": [],
                "compiler": "test cc",
                "linker": "test ld"
            },
            "rust": {
                "source_revision": "test",
                "lockfile_sha256": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
                "target": "x86_64-unknown-linux-gnu",
                "compiler": "test rustc",
                "profile": "debug"
            },
            "api_versions": {
                "runtime_protocol": 1,
                "provider_schema": 1,
                "theme_schema": 1,
                "integration_api": 1
            },
            "entrypoints": {
                "shell": "bin/zsh",
                "runtime": "bin/wsh-runtime",
                "integration": "share/wsh/integration.zsh",
                "default_theme": "share/wsh/themes/minimal.toml"
            },
            "requirements": {"dynamic_libraries": [], "minimum_glibc": null},
            "files": files
        });
        fs::write(
            root.join("manifest.json"),
            serde_json::to_vec_pretty(&manifest).unwrap(),
        )
        .unwrap();
    }

    #[test]
    fn rejects_traversal_and_absolute_paths() {
        for path in ["../bin/zsh", "bin/../zsh", "/bin/zsh", "bin\\zsh", ""] {
            assert!(validate_relative_path(path).is_err(), "accepted {path:?}");
        }
        assert!(validate_relative_path("bin/zsh").is_ok());
    }

    #[test]
    fn rejects_unknown_manifest_fields() {
        let json = r#"{
            "schema_version": 1,
            "status": "development",
            "release_id": "dev",
            "target": "x86_64-unknown-linux-gnu",
            "minimum_manager_version": "0.1.0",
            "builder": {"base_image":null,"package_lock_sha256":null,"rust_toolchain_sha256":null,"source_date_epoch":null,"environment":{"lang":"C","lc_all":"C","tz":"UTC","build_jobs":"1"}},
            "zsh": {"version":"5.9.2","source_archive":"x","source_sha256":"x","signer_fingerprint":"x","source_revision":"x","patches":[],"configure_args":[],"compiler":"x","linker":"x"},
            "rust": {"source_revision":"x","lockfile_sha256":"x","target":"x86_64-unknown-linux-gnu","compiler":"x","profile":"debug"},
            "api_versions": {"runtime_protocol":1,"provider_schema":1,"theme_schema":1,"integration_api":1},
            "entrypoints": {"shell":"bin/zsh","runtime":"bin/wsh-runtime","integration":"share/wsh/integration.zsh","default_theme":"share/wsh/themes/minimal.toml"},
            "requirements": {"dynamic_libraries":[],"minimum_glibc":null},
            "files": [],
            "surprise": true
        }"#;
        assert!(serde_json::from_str::<BundleManifest>(json).is_err());
    }

    #[test]
    fn verifies_an_exact_development_payload_and_detects_tampering() {
        let directory = tempfile::tempdir().unwrap();
        write_test_bundle(directory.path());
        let verified = verify_bundle(directory.path()).unwrap();
        assert_eq!(verified.manifest.status, BundleStatus::Development);
        assert_eq!(verified.manifest_sha256.len(), 64);

        fs::write(directory.path().join("bin/zsh"), b"changed").unwrap();
        let error = verify_bundle(directory.path()).err().unwrap();
        assert!(error.contains("size mismatch") || error.contains("digest mismatch"));
    }

    #[test]
    fn verifies_release_status_as_a_structural_manifest_property() {
        let directory = tempfile::tempdir().unwrap();
        write_test_bundle(directory.path());
        let manifest_path = directory.path().join("manifest.json");
        let mut manifest: serde_json::Value =
            serde_json::from_slice(&fs::read(&manifest_path).unwrap()).unwrap();
        manifest["status"] = serde_json::json!("release");
        manifest["release_id"] = serde_json::json!("v0.1.0");
        fs::write(
            &manifest_path,
            serde_json::to_vec_pretty(&manifest).unwrap(),
        )
        .unwrap();

        let verified = verify_bundle(directory.path()).unwrap();
        assert_eq!(verified.manifest.status, BundleStatus::Release);
        assert_eq!(verified.manifest.release_id, "v0.1.0");
    }

    #[test]
    fn rejects_unlisted_files_and_symbolic_links() {
        let directory = tempfile::tempdir().unwrap();
        write_test_bundle(directory.path());
        fs::write(directory.path().join("unlisted"), b"surprise").unwrap();
        assert!(verify_bundle(directory.path()).is_err());
        fs::remove_file(directory.path().join("unlisted")).unwrap();
        symlink("bin/zsh", directory.path().join("link")).unwrap();
        let error = verify_bundle(directory.path()).err().unwrap();
        assert!(error.contains("symbolic links are not allowed"));
    }

    #[test]
    fn atomically_activates_and_rolls_back_from_a_broken_active_bundle() {
        let directory = tempfile::tempdir().unwrap();
        let first = directory.path().join("first");
        let second = directory.path().join("second");
        let state = directory.path().join("state");
        fs::create_dir(&first).unwrap();
        fs::create_dir(&second).unwrap();
        write_test_bundle(&first);
        write_test_bundle(&second);
        activate_bundle(&state, &first).unwrap();
        activate_bundle(&state, &second).unwrap();
        fs::write(state.join(".bundle-state.json.interrupted.tmp"), b"partial").unwrap();
        fs::write(second.join("bin/zsh"), b"broken").unwrap();
        assert!(active_bundle(&state).is_err());
        rollback_bundle(&state).unwrap();
        assert_eq!(
            active_bundle(&state).unwrap(),
            first.canonicalize().unwrap()
        );
    }

    #[test]
    fn launch_trusts_activation_while_explicit_verification_detects_later_tampering() {
        let directory = tempfile::tempdir().unwrap();
        let bundle = directory.path().join("bundle");
        let state = directory.path().join("state");
        fs::create_dir(&bundle).unwrap();
        write_test_bundle(&bundle);
        activate_bundle(&state, &bundle).unwrap();

        let state_bytes = fs::read(state.join(STATE_FILE_NAME)).unwrap();
        assert!(state_bytes.len() < MAX_STATE_BYTES as usize);
        assert!(
            !state_bytes
                .windows(14)
                .any(|bytes| bytes == b"source_archive")
        );

        fs::write(bundle.join("bin/wsh-runtime"), b"changed").unwrap();
        let launch = active_bundle_for_launch(&state).unwrap();
        assert_eq!(launch.root, bundle.canonicalize().unwrap());
        assert!(verify_bundle(&bundle).is_err());

        fs::remove_file(bundle.join("share/wsh/integration.zsh")).unwrap();
        let error = active_bundle_for_launch(&state).err().unwrap();
        assert!(error.contains("could not inspect share/wsh/integration.zsh"));
    }

    #[test]
    fn detects_swapped_entrypoints_and_manifest_mutation() {
        let directory = tempfile::tempdir().unwrap();
        let bundle = directory.path().join("bundle");
        fs::create_dir(&bundle).unwrap();
        write_test_bundle(&bundle);
        let shell = fs::read(bundle.join("bin/zsh")).unwrap();
        let runtime = fs::read(bundle.join("bin/wsh-runtime")).unwrap();
        fs::write(bundle.join("bin/zsh"), runtime).unwrap();
        fs::write(bundle.join("bin/wsh-runtime"), shell).unwrap();
        assert!(verify_bundle(&bundle).is_err());

        write_test_bundle(&bundle);
        let state = directory.path().join("state");
        activate_bundle(&state, &bundle).unwrap();
        let mut manifest = fs::read(bundle.join("manifest.json")).unwrap();
        manifest.push(b'\n');
        fs::write(bundle.join("manifest.json"), manifest).unwrap();
        active_bundle_for_launch(&state).unwrap();
        let error = active_bundle(&state).unwrap_err();
        assert!(error.contains("manifest digest changed"));
    }
}
