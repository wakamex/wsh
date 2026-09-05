use std::process::Command;

#[test]
fn reports_the_launcher_version_without_active_state() {
    let expected = format!("wsh {}\n", env!("CARGO_PKG_VERSION"));
    let output = Command::new(env!("CARGO_BIN_EXE_wsh"))
        .arg("--version")
        .env_remove("HOME")
        .env_remove("XDG_DATA_HOME")
        .env_remove("WSH_STATE_ROOT")
        .output()
        .expect("wsh should run");
    assert!(output.status.success());
    assert_eq!(String::from_utf8(output.stdout).unwrap(), expected);
    assert!(output.stderr.is_empty());
}

#[test]
fn detailed_version_requires_an_active_bundle() {
    let state = tempfile::tempdir().unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_wsh"))
        .args(["version", "--state-root"])
        .arg(state.path())
        .output()
        .expect("wsh should run");
    assert!(!output.status.success());
    assert!(output.stdout.is_empty());
    assert_eq!(
        String::from_utf8(output.stderr).unwrap(),
        "error: no active bundle state\n"
    );
}
