//! Experimental installation-owned launcher. Management remains a separate tool.
use std::{env, io, os::unix::ffi::OsStrExt, os::unix::process::CommandExt, process::Command};

fn main() -> io::Result<()> {
    let executable = env::current_exe()?;
    let root = executable.parent().unwrap().parent().unwrap();
    let mut arguments = env::args_os();
    let login = arguments.next().unwrap_or_default().as_bytes().starts_with(b"-");
    let mut shell = Command::new(root.join("bin/zsh"));
    // Retain the current launcher's global-startup policy for this control.
    shell.arg("-d");
    if login {
        shell.arg("-l");
    }
    shell.args(arguments);
    if let Some(user_dir) = env::var_os("ZDOTDIR").or_else(|| env::var_os("HOME")) {
        shell.env("WSH_USER_ZDOTDIR", user_dir);
    } else {
        shell.env_remove("WSH_USER_ZDOTDIR");
    }
    shell.env("WSH_BUNDLE_ROOT", root)
        .env("WSH_RUNTIME", root.join("bin/wsh-runtime"))
        .env("WSH_NATIVE_TERMINAL_INTEGRATION", "1")
        .env("ZDOTDIR", root.join("share/wsh/zdotdir"))
        .env_remove("WSH_RUN_FOREGROUND")
        .env_remove("WSH_STARTUP_BUNDLE_ZDOTDIR")
        .env_remove("WSH_STARTUP_RCS");
    Err(shell.exec())
}
