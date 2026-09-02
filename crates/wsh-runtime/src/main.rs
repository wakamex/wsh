use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use wsh_runtime::{load_theme, serve};

fn usage() -> &'static str {
    "usage:\n  wsh-runtime validate-theme <theme.toml>\n  wsh-runtime serve --theme <theme.toml>"
}

fn run() -> Result<(), String> {
    let mut args = env::args_os().skip(1);
    match args
        .next()
        .and_then(|arg| arg.into_string().ok())
        .as_deref()
    {
        Some("validate-theme") => {
            let path = PathBuf::from(args.next().ok_or_else(|| usage().to_owned())?);
            if args.next().is_some() {
                return Err(usage().into());
            }
            let theme = load_theme(&path)?;
            println!("{}", theme.id);
            Ok(())
        }
        Some("serve") => {
            if args.next().as_deref() != Some("--theme".as_ref()) {
                return Err(usage().into());
            }
            let path = PathBuf::from(args.next().ok_or_else(|| usage().to_owned())?);
            if args.next().is_some() {
                return Err(usage().into());
            }
            let theme = load_theme(&path)?;
            serve(theme, std::io::stdin().lock(), std::io::stdout().lock())
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
