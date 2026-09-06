//! Shell-style entry and pre-exec recovery, independent of mutable bundle state.
use std::ffi::{OsStr, OsString};
use std::os::unix::ffi::OsStrExt;
use std::os::unix::process::CommandExt;
use std::process::Command;

pub fn is_shell_invocation(program: &OsStr, args: &[OsString]) -> bool {
    program.as_bytes().starts_with(b"-")
        || args.first().is_some_and(|arg| {
            arg.as_bytes().starts_with(b"-") && arg != "--" && arg != "--version"
        })
}

// Only translate shell options with shared Bash/Zsh semantics. Never reinterpret
// a script file, restricted-shell option, or arbitrary Zsh flag under Bash.
fn recovery_args(login: bool, args: &[OsString]) -> Option<Vec<OsString>> {
    let mut result = vec![OsString::from("--noprofile"), OsString::from("--norc")];
    if login {
        result.push("-l".into());
    }
    let mut index = 0;
    while let Some(arg) = args.get(index) {
        if arg == "--login" {
            result.push("-l".into());
        } else if arg == "--" && index + 1 == args.len() {
            break;
        } else {
            let option = arg.to_str()?.strip_prefix('-')?;
            if option.is_empty() || !option.bytes().all(|c| b"lics".contains(&c)) {
                return None;
            }
            // The command string and all subsequent argv bytes are opaque.
            if option.contains('c') {
                args.get(index + 1)?;
                result.push(arg.clone());
                result.extend_from_slice(&args[index + 1..]);
                return Some(result);
            }
            result.push(arg.clone());
        }
        index += 1;
    }
    Some(result)
}

pub fn run(program: &OsStr, args: &[OsString]) -> Result<(), String> {
    let login = program.as_bytes().starts_with(b"-");
    let launch = (|| {
        let launch = wsh::active_bundle_for_launch(&super::default_state_root()?)?;
        let mut command = super::configured_shell(&launch.root, &launch.entrypoints);
        if login {
            command.arg("-l");
        }
        command.args(args);
        let error = command.exec();
        Err::<(), String>(format!(
            "could not execute {}: {error}",
            launch.entrypoints.shell.display()
        ))
    })();
    let error = launch.expect_err("successful exec never returns");
    let Some(arguments) = recovery_args(login, args) else {
        return Err(format!(
            "{error}; these shell arguments cannot be safely recovered with system Bash"
        ));
    };
    eprintln!(
        "wsh: {error}\nwsh: starting system Bash recovery with startup files disabled.\n\
         Keep /bin/bash or system Zsh as your account login shell; repair Wsh from there."
    );
    let mut command = Command::new("/bin/bash");
    command.args(arguments);
    for (key, _) in std::env::vars_os() {
        if key.as_bytes().starts_with(b"WSH_") || key.as_bytes().starts_with(b"BASH_FUNC_") {
            command.env_remove(key);
        }
    }
    command
        .env_remove("BASH_ENV")
        .env_remove("ENV")
        .env_remove("PROMPT_COMMAND")
        .env_remove("PS0")
        .env_remove("BASHOPTS")
        .env_remove("SHELLOPTS")
        .env_remove("ZDOTDIR")
        .env("SHELL", "/bin/bash")
        .env("PS1", "wsh recovery$ ");
    let recovery_error = command.exec();
    Err(format!(
        "{error}; could not execute system Bash recovery: {recovery_error}"
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn args(values: &[&str]) -> Vec<OsString> {
        values.iter().map(OsString::from).collect()
    }

    #[test]
    fn distinguishes_shell_entry_from_manager_commands() {
        for input in [&["-c", "true"][..], &["-lc", "true"], &["--login"]] {
            assert!(is_shell_invocation(OsStr::new("wsh"), &args(input)));
        }
        assert!(is_shell_invocation(OsStr::new("-wsh"), &[]));
        for input in [
            &[][..],
            &["run"],
            &["update"],
            &["--version"],
            &["--", "echo"],
        ] {
            assert!(!is_shell_invocation(OsStr::new("wsh"), &args(input)));
        }
    }

    #[test]
    fn recovery_preserves_command_tail_and_rejects_ambiguous_options() {
        assert_eq!(
            recovery_args(true, &args(&["-c", "printf '%s' \"$1\"", "name", "-r"])),
            Some(args(&[
                "--noprofile",
                "--norc",
                "-l",
                "-c",
                "printf '%s' \"$1\"",
                "name",
                "-r"
            ]))
        );
        for input in [
            &["-r"][..],
            &["-o", "restricted"],
            &["script.zsh"],
            &["-c"],
            &["--", "script.zsh"],
            &["-f"],
        ] {
            assert!(recovery_args(true, &args(input)).is_none(), "{input:?}");
        }
    }
}
