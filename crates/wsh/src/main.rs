use std::env;
use std::path::PathBuf;
use std::process::{Command, ExitCode};

use wsh::{entrypoints, verify_bundle};

fn usage() -> &'static str {
    "usage:\n  wsh bundle verify <bundle>\n  wsh run --bundle <bundle> [-- <zsh arguments...>]"
}

fn run() -> Result<(), String> {
    let mut args = env::args_os().skip(1);
    match args
        .next()
        .and_then(|arg| arg.into_string().ok())
        .as_deref()
    {
        Some("bundle") => {
            if args.next().as_deref() != Some("verify".as_ref()) {
                return Err(usage().into());
            }
            let bundle = PathBuf::from(args.next().ok_or_else(|| usage().to_owned())?);
            if args.next().is_some() {
                return Err(usage().into());
            }
            let verified = verify_bundle(&bundle)?;
            println!("{}", verified.manifest_sha256);
            Ok(())
        }
        Some("run") => {
            if args.next().as_deref() != Some("--bundle".as_ref()) {
                return Err(usage().into());
            }
            let bundle = PathBuf::from(args.next().ok_or_else(|| usage().to_owned())?);
            let remaining: Vec<_> = args.collect();
            let shell_args = match remaining.first().and_then(|arg| arg.to_str()) {
                Some("--") => &remaining[1..],
                _ => &remaining[..],
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
