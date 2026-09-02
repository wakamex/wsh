use std::env;
use std::path::PathBuf;
use std::process::{Command, ExitCode};

use wsh::{activate_bundle, active_bundle, entrypoints, rollback_bundle, verify_bundle};

fn usage() -> &'static str {
    "usage:\n  wsh bundle verify <bundle>\n  wsh bundle activate <bundle> [--state-root <directory>]\n  wsh bundle rollback [--state-root <directory>]\n  wsh bundle current [--state-root <directory>]\n  wsh run [--bundle <bundle>] [--state-root <directory>] [-- <zsh arguments...>]"
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
            let bundle = match bundle {
                Some(bundle) => bundle,
                None => active_bundle(&state_root.unwrap_or(default_state_root()?))?,
            };
            let verified = verify_bundle(&bundle)?;
            let paths = entrypoints(&bundle, &verified.manifest);
            let mut command = Command::new(&paths.shell);
            if shell_args.is_empty() {
                command.arg("-d");
            } else {
                command.args(shell_args);
            }
            let status = command
                .env("WSH_BUNDLE_ROOT", &bundle)
                .env("WSH_RUNTIME", &paths.runtime)
                .env("WSH_THEME", &paths.default_theme)
                .env("ZDOTDIR", &paths.zdotdir)
                .status()
                .map_err(|error| format!("could not start {}: {error}", paths.shell.display()))?;
            if status.success() {
                Ok(())
            } else {
                Err(format!("bundled Zsh exited with {status}"))
            }
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
