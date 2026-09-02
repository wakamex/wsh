use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use wsh_install::{InstallRequest, install_release};

fn usage() -> &'static str {
    "usage:\n  wsh-install install --archive <path> --attestation <path> --tag <vMAJOR.MINOR.PATCH> --commit <40-hex-sha> [--install-root <directory>] [--state-root <directory>] [--allow-downgrade]"
}

fn default_data_root() -> Result<PathBuf, String> {
    if let Some(path) = env::var_os("WSH_STATE_ROOT") {
        return Ok(PathBuf::from(path));
    }
    if let Some(path) = env::var_os("XDG_DATA_HOME") {
        return Ok(PathBuf::from(path).join("wsh"));
    }
    env::var_os("HOME")
        .map(|path| PathBuf::from(path).join(".local/share/wsh"))
        .ok_or_else(|| "HOME, XDG_DATA_HOME, or WSH_STATE_ROOT is required".into())
}

fn run() -> Result<(), String> {
    let mut args = env::args_os().skip(1);
    if args.next().as_deref() != Some(std::ffi::OsStr::new("install")) {
        return Err(usage().into());
    }

    let mut archive = None;
    let mut attestation = None;
    let mut tag = None;
    let mut commit = None;
    let mut install_root = None;
    let mut state_root = None;
    let mut allow_downgrade = false;
    while let Some(flag) = args.next() {
        if flag == "--allow-downgrade" {
            allow_downgrade = true;
            continue;
        }
        let value = args.next().ok_or_else(|| usage().to_owned())?;
        match flag.to_str() {
            Some("--archive") => archive = Some(PathBuf::from(value)),
            Some("--attestation") => attestation = Some(PathBuf::from(value)),
            Some("--tag") => {
                tag = Some(
                    value
                        .into_string()
                        .map_err(|_| "release tag must be UTF-8".to_owned())?,
                )
            }
            Some("--commit") => {
                commit = Some(
                    value
                        .into_string()
                        .map_err(|_| "source commit must be UTF-8".to_owned())?,
                )
            }
            Some("--install-root") => install_root = Some(PathBuf::from(value)),
            Some("--state-root") => state_root = Some(PathBuf::from(value)),
            _ => return Err(usage().into()),
        }
    }

    let data_root = default_data_root()?;
    let result = install_release(&InstallRequest {
        archive: archive.ok_or_else(|| usage().to_owned())?,
        attestation: attestation.ok_or_else(|| usage().to_owned())?,
        tag: tag.ok_or_else(|| usage().to_owned())?,
        commit: commit.ok_or_else(|| usage().to_owned())?,
        install_root: install_root.unwrap_or_else(|| data_root.clone()),
        state_root: state_root.unwrap_or(data_root),
        allow_downgrade,
    })?;
    println!("{}", result.bundle.display());
    Ok(())
}

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("error: {error}");
            ExitCode::FAILURE
        }
    }
}
