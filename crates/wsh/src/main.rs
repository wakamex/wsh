use std::env;
use std::ffi::OsString;
use std::os::unix::process::CommandExt;
use std::path::PathBuf;
use std::process::{Command, ExitCode};

use wsh::{
    BundleStatus, activate_bundle, active_bundle, active_bundle_for_launch, entrypoints,
    rollback_bundle, verify_bundle,
};

mod doctor;
mod update;

fn usage() -> &'static str {
    "usage:\n  wsh\n  wsh bundle verify <bundle>\n  wsh bundle activate <bundle> [--state-root <directory>]\n  wsh bundle rollback [--state-root <directory>]\n  wsh bundle current [--state-root <directory>]\n  wsh doctor [--state-root <directory>]\n  wsh update [--check | --to vMAJOR.MINOR.PATCH] [--state-root <directory>]\n  wsh run [--bundle <bundle>] [--state-root <directory>] [-- <zsh arguments...>]"
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

fn select_user_zdotdir(
    configured: Option<OsString>,
    inherited_bundle_root: Option<OsString>,
    inherited_user_zdotdir: Option<OsString>,
    home: Option<OsString>,
) -> Option<OsString> {
    let inherited_bundle_zdotdir = inherited_bundle_root
        .map(PathBuf::from)
        .map(|root| root.join("share/wsh/zdotdir"));
    match configured {
        Some(path)
            if inherited_bundle_zdotdir
                .as_ref()
                .is_some_and(|bundle| PathBuf::from(&path) == *bundle) =>
        {
            inherited_user_zdotdir.or(home)
        }
        Some(path) => Some(path),
        None => home,
    }
}

fn user_zdotdir() -> Option<OsString> {
    select_user_zdotdir(
        env::var_os("ZDOTDIR"),
        env::var_os("WSH_BUNDLE_ROOT"),
        env::var_os("WSH_USER_ZDOTDIR"),
        env::var_os("HOME"),
    )
}

fn run() -> Result<(), String> {
    let mut args = env::args_os().skip(1);
    let action = args
        .next()
        .map(|arg| arg.into_string())
        .transpose()
        .map_err(|_| usage().to_owned())?;
    let action = action.as_deref().unwrap_or("run");
    match action {
        "bundle" => {
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
        "run" => {
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
            command.arg("-d").args(shell_args);
            if let Some(user_zdotdir) = user_zdotdir() {
                command.env("WSH_USER_ZDOTDIR", user_zdotdir);
            } else {
                command.env_remove("WSH_USER_ZDOTDIR");
            }
            command
                .env("WSH_BUNDLE_ROOT", &bundle)
                .env("WSH_RUNTIME", &paths.runtime)
                .env("WSH_THEME", &paths.default_theme)
                .env("ZDOTDIR", &paths.zdotdir)
                .env_remove("WSH_STARTUP_BUNDLE_ZDOTDIR")
                .env_remove("WSH_STARTUP_RCS");
            let error = command.exec();
            Err(format!(
                "could not replace the launcher with {}: {error}",
                paths.shell.display()
            ))
        }
        "update" => {
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
        "doctor" => {
            let remaining: Vec<_> = args.collect();
            let state_root = parse_state_root(&remaining)?;
            let launch = active_bundle_for_launch(&state_root)?;
            let user_zdotdir = user_zdotdir();
            doctor::run(doctor::Shell {
                executable: &launch.entrypoints.shell,
                bundle_root: &launch.root,
                runtime: &launch.entrypoints.runtime,
                theme: &launch.entrypoints.default_theme,
                zdotdir: &launch.entrypoints.zdotdir,
                user_zdotdir: user_zdotdir.as_deref(),
            })
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

#[cfg(test)]
mod tests {
    use super::select_user_zdotdir;
    use std::ffi::OsString;

    fn value(value: &str) -> Option<OsString> {
        Some(OsString::from(value))
    }

    #[test]
    fn preserves_explicit_user_zdotdir() {
        assert_eq!(
            select_user_zdotdir(value("/user/config"), None, None, value("/home/user")),
            value("/user/config")
        );
    }

    #[test]
    fn recovers_user_zdotdir_inherited_from_an_older_wsh_session() {
        assert_eq!(
            select_user_zdotdir(
                value("/old-bundle/share/wsh/zdotdir"),
                value("/old-bundle"),
                value("/user/config"),
                value("/home/user"),
            ),
            value("/user/config")
        );
    }

    #[test]
    fn uses_home_when_zdotdir_is_unset_or_only_the_old_bundle_is_known() {
        assert_eq!(
            select_user_zdotdir(None, None, None, value("/home/user")),
            value("/home/user")
        );
        assert_eq!(
            select_user_zdotdir(
                value("/old-bundle/share/wsh/zdotdir"),
                value("/old-bundle"),
                None,
                value("/home/user"),
            ),
            value("/home/user")
        );
    }
}
