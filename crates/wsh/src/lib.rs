use std::collections::HashSet;
use std::fs::{self, File};
use std::io::{BufReader, Read};
use std::os::unix::fs::MetadataExt;
use std::path::{Component, Path, PathBuf};

use serde::Deserialize;
use sha2::{Digest, Sha256};

const MANIFEST_NAME: &str = "manifest.json";
const MAX_MANIFEST_BYTES: u64 = 1024 * 1024;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BundleManifest {
    pub schema_version: u32,
    pub status: BundleStatus,
    pub release_id: String,
    pub target: String,
    pub minimum_manager_version: String,
    pub zsh: ZshBuild,
    pub rust: RustBuild,
    pub api_versions: ApiVersions,
    pub entrypoints: Entrypoints,
    pub requirements: Requirements,
    pub files: Vec<PayloadFile>,
}

#[derive(Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum BundleStatus {
    Development,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ZshBuild {
    pub version: String,
    pub source_archive: String,
    pub source_sha256: String,
    pub signer_fingerprint: String,
    pub source_revision: String,
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
    pub default_theme: PathBuf,
    pub zdotdir: PathBuf,
}

pub fn verify_bundle(root: &Path) -> Result<VerifiedBundle, String> {
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

    for path in [
        &manifest.entrypoints.shell,
        &manifest.entrypoints.runtime,
        &manifest.entrypoints.integration,
        &manifest.entrypoints.default_theme,
    ] {
        if !listed.contains(path) {
            return Err(format!(
                "entrypoint is not listed as a payload file: {path}"
            ));
        }
    }

    Ok(VerifiedBundle {
        manifest,
        manifest_sha256: sha256_bytes(&manifest_bytes),
    })
}

pub fn entrypoints(root: &Path, manifest: &BundleManifest) -> EntrypointPaths {
    EntrypointPaths {
        shell: root.join(&manifest.entrypoints.shell),
        runtime: root.join(&manifest.entrypoints.runtime),
        default_theme: root.join(&manifest.entrypoints.default_theme),
        zdotdir: root.join("share/wsh/zdotdir"),
    }
}

fn validate_manifest(manifest: &BundleManifest) -> Result<(), String> {
    if manifest.schema_version != 1 {
        return Err(format!(
            "unsupported manifest schema version: {}",
            manifest.schema_version
        ));
    }
    if manifest.status != BundleStatus::Development {
        return Err("only unsigned development bundles are supported".into());
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

    let path = root.join(&expected.path);
    let metadata = fs::symlink_metadata(&path)
        .map_err(|error| format!("could not inspect {}: {error}", expected.path))?;
    if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
        return Err(format!("payload is not a regular file: {}", expected.path));
    }
    if metadata.len() != expected.size {
        return Err(format!("size mismatch for {}", expected.path));
    }
    if metadata.mode() & 0o7777 != expected.mode {
        return Err(format!("mode mismatch for {}", expected.path));
    }
    let actual_digest = sha256_file(&path)?;
    if actual_digest != expected.sha256 {
        return Err(format!("digest mismatch for {}", expected.path));
    }
    Ok(())
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
}
