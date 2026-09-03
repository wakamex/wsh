use std::env;
use std::os::unix::process::CommandExt;
use std::path::PathBuf;
use std::process::{Command, ExitCode};

use wsh::{
    BundleStatus, activate_bundle, active_bundle, active_bundle_for_launch, entrypoints,
    rollback_bundle, verify_bundle,
};

mod update;

fn usage() -> &'static str {
    "usage:\n  wsh bundle verify <bundle>\n  wsh bundle activate <bundle> [--state-root <directory>]\n  wsh bundle rollback [--state-root <directory>]\n  wsh bundle current [--state-root <directory>]\n  wsh update [--check | --to vMAJOR.MINOR.PATCH] [--state-root <directory>]\n  wsh run [--bundle <bundle>] [--state-root <directory>] [-- <zsh arguments...>]"
}

fn default_state_root() -> Result<PathBuf, String> {
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

fn parse_state_root(arguments: &[std::ffi::OsString]) -> Result<PathBuf, String> {
    match arguments {
        [] => default_state_root(),
        [option, path] if option == "--state-root" => Ok(PathBuf::from(path)),
        _ => Err(usage().into()),
    }
}

fn run() -> Result<(), String> {
    let mut args = env::args_os().skip(1);
    match args
        .next()
        .and_then(|arg| arg.into_string().ok())
        .as_deref()
    {
        Some("bundle") => {
            let action = args
                .next()
                .and_then(|arg| arg.into_string().ok())
                .ok_or_else(|| usage().to_owned())?;
            let remaining: Vec<_> = args.collect();
            match action.as_str() {
                "verify" => {
                    let [bundle] = remaining.as_slice() else {
                        return Err(usage().into());
                    };
                    let verified = verify_bundle(&PathBuf::from(bundle))?;
                    println!("{}", verified.manifest_sha256);
                }
                "activate" => {
                    let bundle = remaining.first().ok_or_else(|| usage().to_owned())?;
                    let state_root = parse_state_root(&remaining[1..])?;
                    println!("{}", activate_bundle(&state_root, &PathBuf::from(bundle))?);
                }
                "rollback" => {
                    let state_root = parse_state_root(&remaining)?;
                    println!("{}", rollback_bundle(&state_root)?);
                }
                "current" => {
                    let state_root = parse_state_root(&remaining)?;
                    println!("{}", active_bundle(&state_root)?.display());
                }
                _ => return Err(usage().into()),
            }
            Ok(())
        }
        Some("run") => {
            let remaining: Vec<_> = args.collect();
            let separator = remaining.iter().position(|arg| arg == "--");
            let (options, shell_args) = separator.map_or((&remaining[..], &[][..]), |index| {
                (&remaining[..index], &remaining[index + 1..])
            });
            let mut bundle = None;
            let mut state_root = None;
            let mut index = 0;
            while index < options.len() {
                let value = options.get(index + 1).ok_or_else(|| usage().to_owned())?;
                match options[index].to_str() {
                    Some("--bundle") => bundle = Some(PathBuf::from(value)),
                    Some("--state-root") => state_root = Some(PathBuf::from(value)),
                    _ => return Err(usage().into()),
                }
                index += 2;
            }
            let (bundle, paths) = match bundle {
                Some(bundle) => {
                    let verified = verify_bundle(&bundle)?;
                    let paths = entrypoints(&bundle, &verified.manifest);
                    (bundle, paths)
                }
                None => {
                    let launch =
                        active_bundle_for_launch(&state_root.unwrap_or(default_state_root()?))?;
                    (launch.root, launch.entrypoints)
                }
            };
            let mut command = Command::new(&paths.shell);
            if shell_args.is_empty() {
                command.arg("-d");
            } else {
                command.args(shell_args);
            }
            command
                .env("WSH_BUNDLE_ROOT", &bundle)
                .env("WSH_RUNTIME", &paths.runtime)
                .env("WSH_THEME", &paths.default_theme)
                .env("ZDOTDIR", &paths.zdotdir);
            let error = command.exec();
            Err(format!(
                "could not replace the launcher with {}: {error}",
                paths.shell.display()
            ))
        }
        Some("update") => {
            let remaining: Vec<_> = args.collect();
            let mut check = false;
            let mut target = None;
            let mut state_root = None;
            let mut index = 0;
            while index < remaining.len() {
                match remaining[index].to_str() {
                    Some("--check") => {
                        if check {
                            return Err(usage().into());
                        }
                        check = true;
                        index += 1;
                    }
                    Some("--to") => {
                        if target.is_some() {
                            return Err(usage().into());
                        }
                        let value = remaining.get(index + 1).ok_or_else(|| usage().to_owned())?;
                        target = Some(
                            value
                                .to_str()
                                .ok_or_else(|| "release tag must be UTF-8".to_owned())?
                                .to_owned(),
                        );
                        index += 2;
                    }
                    Some("--state-root") => {
                        if state_root.is_some() {
                            return Err(usage().into());
                        }
                        let value = remaining.get(index + 1).ok_or_else(|| usage().to_owned())?;
                        state_root = Some(PathBuf::from(value));
                        index += 2;
                    }
                    _ => return Err(usage().into()),
                }
            }
            if check && target.is_some() {
                return Err(usage().into());
            }
            let state_root = state_root.unwrap_or(default_state_root()?);
            let bundle = active_bundle(&state_root)?;
            let verified = verify_bundle(&bundle)?;
            if verified.manifest.status != BundleStatus::Release {
                return Err("updates require an active official release bundle".into());
            }
            let mode = if check {
                update::UpdateMode::Check
            } else if let Some(target) = target {
                update::UpdateMode::Exact(target)
            } else {
                update::UpdateMode::Latest
            };
            update::run(mode, &verified.manifest.release_id, &state_root)
        }
        _ => Err(usage().into()),
    }
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
