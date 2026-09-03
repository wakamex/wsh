use std::cmp::Ordering;
use std::env;
use std::fs::{self, DirBuilder};
use std::os::unix::fs::DirBuilderExt;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

const LATEST_RELEASE_URL: &str = "https://github.com/wakamex/wsh/releases/latest";
const RELEASE_TAG_URL_PREFIX: &str = "https://github.com/wakamex/wsh/releases/tag/";
const RELEASE_DOWNLOAD_URL_PREFIX: &str = "https://github.com/wakamex/wsh/releases/download/";

#[derive(Clone, Copy, Debug, Eq, Ord, PartialEq, PartialOrd)]
struct ReleaseVersion {
    major: u64,
    minor: u64,
    patch: u64,
}

pub enum UpdateMode {
    Latest,
    Check,
    Exact(String),
}

pub fn run(mode: UpdateMode, current_tag: &str, state_root: &Path) -> Result<(), String> {
    let current = parse_release_tag(current_tag)?;
    let (target_tag, check_only) = match mode {
        UpdateMode::Latest => (latest_release_tag()?, false),
        UpdateMode::Check => (latest_release_tag()?, true),
        UpdateMode::Exact(tag) => {
            parse_release_tag(&tag)?;
            (tag, false)
        }
    };
    let target = parse_release_tag(&target_tag)?;

    match target.cmp(&current) {
        Ordering::Less => {
            if check_only {
                println!("wsh {current_tag} is newer than GitHub's current {target_tag} release.");
                Ok(())
            } else {
                Err(format!(
                    "refusing to update from {current_tag} to older release {target_tag}; use `wsh bundle rollback` to select the previous installed bundle"
                ))
            }
        }
        Ordering::Equal => {
            println!("wsh {current_tag} is up to date.");
            Ok(())
        }
        Ordering::Greater if check_only => {
            println!("wsh {target_tag} is available; current release is {current_tag}.");
            Ok(())
        }
        Ordering::Greater => install_release(&target_tag, state_root),
    }
}

fn latest_release_tag() -> Result<String, String> {
    let output = Command::new("curl")
        .args([
            "--disable",
            "--proto",
            "=https",
            "--proto-redir",
            "=https",
            "--tlsv1.2",
            "--fail",
            "--location",
            "--retry",
            "3",
            "--silent",
            "--show-error",
            "--output",
            "/dev/null",
            "--write-out",
            "%{url_effective}",
            "--",
            LATEST_RELEASE_URL,
        ])
        .output()
        .map_err(|error| format!("could not start curl to check for updates: {error}"))?;
    if !output.status.success() {
        return Err(format_command_failure(
            "could not check GitHub's current wsh release",
            &output.stderr,
        ));
    }
    if output.stdout.len() > 1024 {
        return Err("GitHub's latest-release redirect URL exceeds 1024 bytes".into());
    }
    let effective_url = std::str::from_utf8(&output.stdout)
        .map_err(|_| "GitHub's latest-release redirect URL is not UTF-8".to_owned())?;
    parse_latest_release_url(effective_url.trim())
}

fn install_release(tag: &str, state_root: &Path) -> Result<(), String> {
    let temporary = PrivateTemporaryDirectory::new()?;
    let bootstrap = temporary.path().join(format!("wsh-{tag}-install.sh"));
    let url = release_bootstrap_url(tag)?;
    let output = Command::new("curl")
        .args([
            "--disable",
            "--proto",
            "=https",
            "--proto-redir",
            "=https",
            "--tlsv1.2",
            "--fail",
            "--location",
            "--retry",
            "3",
            "--silent",
            "--show-error",
            "--output",
        ])
        .arg(&bootstrap)
        .arg("--")
        .arg(&url)
        .output()
        .map_err(|error| format!("could not start curl to download {tag}: {error}"))?;
    if !output.status.success() {
        return Err(format_command_failure(
            &format!("could not download the {tag} release bootstrap"),
            &output.stderr,
        ));
    }

    let status = Command::new("sh")
        .arg(&bootstrap)
        .env("WSH_STATE_ROOT", state_root)
        .status()
        .map_err(|error| format!("could not start the {tag} release bootstrap: {error}"))?;
    if !status.success() {
        return Err(format!(
            "{tag} release bootstrap failed with {}",
            status_description(status.code())
        ));
    }
    Ok(())
}

fn release_bootstrap_url(tag: &str) -> Result<String, String> {
    parse_release_tag(tag)?;
    Ok(format!(
        "{RELEASE_DOWNLOAD_URL_PREFIX}{tag}/wsh-{tag}-install.sh"
    ))
}

fn parse_latest_release_url(url: &str) -> Result<String, String> {
    let tag = url.strip_prefix(RELEASE_TAG_URL_PREFIX).ok_or_else(|| {
        format!("GitHub redirected the latest release to an unexpected URL: {url}")
    })?;
    parse_release_tag(tag)?;
    Ok(tag.to_owned())
}

fn parse_release_tag(tag: &str) -> Result<ReleaseVersion, String> {
    let version = tag
        .strip_prefix('v')
        .ok_or_else(|| format!("release tag must be canonical vMAJOR.MINOR.PATCH: {tag}"))?;
    let mut parts = version.split('.');
    let major = parse_version_component(parts.next(), tag)?;
    let minor = parse_version_component(parts.next(), tag)?;
    let patch = parse_version_component(parts.next(), tag)?;
    if parts.next().is_some() {
        return Err(format!(
            "release tag must be canonical vMAJOR.MINOR.PATCH: {tag}"
        ));
    }
    Ok(ReleaseVersion {
        major,
        minor,
        patch,
    })
}

fn parse_version_component(component: Option<&str>, tag: &str) -> Result<u64, String> {
    let component = component
        .filter(|component| {
            !component.is_empty()
                && component.bytes().all(|byte| byte.is_ascii_digit())
                && (component == &"0" || !component.starts_with('0'))
        })
        .ok_or_else(|| format!("release tag must be canonical vMAJOR.MINOR.PATCH: {tag}"))?;
    component
        .parse()
        .map_err(|_| format!("release tag component is too large: {tag}"))
}

fn format_command_failure(message: &str, stderr: &[u8]) -> String {
    let detail = String::from_utf8_lossy(stderr);
    let detail = detail.trim();
    if detail.is_empty() {
        message.to_owned()
    } else {
        format!("{message}: {detail}")
    }
}

fn status_description(code: Option<i32>) -> String {
    code.map_or_else(
        || "a signal".to_owned(),
        |code| format!("exit status {code}"),
    )
}

struct PrivateTemporaryDirectory {
    path: PathBuf,
}

impl PrivateTemporaryDirectory {
    fn new() -> Result<Self, String> {
        let base = env::temp_dir();
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|error| format!("system clock is before the Unix epoch: {error}"))?
            .as_nanos();
        for attempt in 0..128_u8 {
            let path = base.join(format!(
                "wsh-update.{}.{}.{}",
                std::process::id(),
                timestamp,
                attempt
            ));
            match DirBuilder::new().mode(0o700).create(&path) {
                Ok(()) => return Ok(Self { path }),
                Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(error) => {
                    return Err(format!(
                        "could not create private update directory {}: {error}",
                        path.display()
                    ));
                }
            }
        }
        Err(format!(
            "could not allocate a private update directory beneath {}",
            base.display()
        ))
    }

    fn path(&self) -> &Path {
        &self.path
    }
}

impl Drop for PrivateTemporaryDirectory {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.path);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::PermissionsExt;

    #[test]
    fn accepts_and_orders_canonical_release_tags() {
        assert!(parse_release_tag("v0.1.3").unwrap() < parse_release_tag("v0.2.0").unwrap());
        assert!(parse_release_tag("v2.0.0").unwrap() > parse_release_tag("v1.99.99").unwrap());
        for invalid in [
            "0.1.3",
            "v0.1",
            "v0.1.3.0",
            "v00.1.3",
            "v0.01.3",
            "v0.1.03",
            "v0.1.x",
            "v0.1.3-rc.1",
            "v0.1.3/",
        ] {
            assert!(parse_release_tag(invalid).is_err(), "accepted {invalid}");
        }
    }

    #[test]
    fn accepts_only_the_exact_github_latest_release_path() {
        assert_eq!(
            parse_latest_release_url("https://github.com/wakamex/wsh/releases/tag/v1.2.3").unwrap(),
            "v1.2.3"
        );
        for invalid in [
            "https://github.com/other/wsh/releases/tag/v1.2.3",
            "https://github.com/wakamex/wsh/releases/tag/v1.2.3/",
            "https://github.com/wakamex/wsh/releases/tag/v1.2.3?x=1",
            "https://example.com/wakamex/wsh/releases/tag/v1.2.3",
        ] {
            assert!(
                parse_latest_release_url(invalid).is_err(),
                "accepted {invalid}"
            );
        }
    }

    #[test]
    fn constructs_only_exact_release_bootstrap_urls() {
        assert_eq!(
            release_bootstrap_url("v1.2.3").unwrap(),
            "https://github.com/wakamex/wsh/releases/download/v1.2.3/wsh-v1.2.3-install.sh"
        );
        assert!(release_bootstrap_url("latest").is_err());
    }

    #[test]
    fn private_temporary_directory_is_removed_on_drop() {
        let path = {
            let temporary = PrivateTemporaryDirectory::new().unwrap();
            assert!(temporary.path().is_dir());
            assert_eq!(
                fs::metadata(temporary.path()).unwrap().permissions().mode() & 0o777,
                0o700
            );
            temporary.path().to_owned()
        };
        assert!(!path.exists());
    }
}
