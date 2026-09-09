use super::*;
use std::io::BufReader;
use std::os::unix::ffi::OsStringExt;
use std::process::{Command, Stdio};

#[test]
#[ignore = "requires WSH_RENDER_DRIVER and WSH_RENDER_OUTPUT"]
fn native_renderer_matches_rust() {
    let driver = std::env::var_os("WSH_RENDER_DRIVER").expect("C driver");
    let output_path = std::env::var_os("WSH_RENDER_OUTPUT").expect("result path");
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let mut records = Vec::new();
    let benchmark = std::env::var_os("WSH_RENDER_BENCHMARK").is_some();
    let fixtures = tempfile::tempdir().unwrap();
    let mut themes: Vec<(String, PathBuf)> = ["minimal", "wakamex", "robbyrussell", "agnoster"]
        .into_iter()
        .map(|name| (name.into(), root.join(format!("themes/{name}.toml"))))
        .collect();
    if !benchmark {
        let source = std::fs::read_to_string(root.join("themes/minimal.toml")).unwrap();
        for limit in [0, 1, 2, 7, 4096] {
            let name = format!("truncate-{limit}");
            let path = fixtures.path().join(format!("{name}.toml"));
            std::fs::write(
                &path,
                source
                    .replace("max-length = 80", &format!("max-length = {limit}"))
                    .replace("style = \"short\"", "style = \"full\""),
            )
            .unwrap();
            themes.push((name, path));
        }
        for color in [
            "default",
            "black",
            "red",
            "green",
            "yellow",
            "blue",
            "magenta",
            "cyan",
            "white",
            "bright-black",
            "bright-red",
            "bright-green",
            "bright-yellow",
            "bright-blue",
            "bright-magenta",
            "bright-cyan",
            "bright-white",
        ] {
            let name = format!("partial-{color}");
            let path = fixtures.path().join(format!("{name}.toml"));
            std::fs::write(
                &path,
                format!(
                    "{}\n[segments.git]\nbackground = \"{color}\"\ndirty-background = \"red\"\n",
                    source.replace("color = \"blue\"", &format!("color = \"{color}\""))
                ),
            )
            .unwrap();
            themes.push((name, path));
        }
    }
    let long_path = format!("/repo/{}", "αβ".repeat(800));
    let paths: &[&[u8]] = &[
        b"/home/wsh",
        b"/repo/path",
        b"/repo/./path//",
        b"/repo/..",
        b"/",
        b"/repo/line\n%F{red}$()`\\",
        b"/repo/\xff",
        "/repo/αβγ".as_bytes(),
        long_path.as_bytes(),
    ];
    let labels = [
        "main",
        "master",
        "feature",
        "",
        "topic/%F{red}$(id)`x`\\",
        "line\n\u{0085}tail",
        "αβγ",
    ];
    for (index, (name, theme_path)) in themes.into_iter().enumerate() {
        for environment in 0..if benchmark || index >= 4 { 1 } else { 4 } {
            let home = if environment == 3 {
                b"/repo/\xff".as_slice()
            } else {
                b"/home/wsh/./".as_slice()
            };
            let user = if environment == 2 {
                b"bad\xff".as_slice()
            } else {
                b"user%F{red}$()".as_slice()
            };
            let host = if environment == 2 {
                b"bad\xff".as_slice()
            } else {
                b"host`id`".as_slice()
            };
            let ssh = environment == 1;
            let mut renderer = Renderer {
                theme: load_theme(&theme_path).unwrap(),
                home: Some(PathBuf::from(std::ffi::OsString::from_vec(home.to_vec()))),
                user: String::from_utf8(user.to_vec()).unwrap_or_default(),
                host: String::from_utf8(host.to_vec()).unwrap_or_else(|_| "localhost".into()),
                ssh,
                last_cwd_hex: None,
                last_git_key: None,
            };
            let mut command = Command::new(&driver);
            command
                .arg(&theme_path)
                .env_clear()
                .env("HOME", std::ffi::OsString::from_vec(home.to_vec()))
                .env("USER", std::ffi::OsString::from_vec(user.to_vec()))
                .env("HOST", std::ffi::OsString::from_vec(host.to_vec()))
                .env("ASAN_OPTIONS", "detect_leaks=1:abort_on_error=1")
                .env("UBSAN_OPTIONS", "halt_on_error=1");
            if ssh {
                command.env("SSH_CONNECTION", "");
            }
            let mut child = command
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .spawn()
                .unwrap();
            let mut input = child.stdin.take().unwrap();
            let mut output = BufReader::new(child.stdout.take().unwrap());
            for case in 0..if benchmark { 1001 } else { 1200 } {
                let snapshot = GitSnapshot {
                    schema_version: 1,
                    generation: case + 1,
                    cwd_hex: encode_hex(paths[(case as usize / 3) % paths.len()]),
                    found: case % 11 != 0,
                    root_hex: Some(encode_hex(if case % 13 == 0 {
                        b"/other"
                    } else {
                        b"/repo"
                    })),
                    branch: (case % 5 != 0)
                        .then(|| labels[(case as usize / 3) % labels.len()].into()),
                    detached_sha: Some("abcdef0".into()),
                    exact_tag: (case % 10 == 0).then(|| "v1%$()".into()),
                    staged: case % 2 != 0,
                    modified: case % 3 == 0,
                    untracked: case % 4 == 0,
                    ahead: if case % 6 == 0 { u64::MAX } else { 0 },
                    behind: if case % 7 == 0 { 2 } else { 0 },
                    operation: [
                        None,
                        Some(GitOperation::Rebase),
                        Some(GitOperation::Merge),
                        Some(GitOperation::CherryPick),
                        Some(GitOperation::Revert),
                        Some(GitOperation::Bisect),
                    ][case as usize % 6],
                    worktree: true,
                };
                let duration = [
                    None,
                    Some(0),
                    Some(1999),
                    Some(2000),
                    Some(61000),
                    Some(86401000),
                    Some(u64::MAX),
                ][case as usize % 7];
                let status = if case % 3 == 0 { -1 } else { 0 };
                let privileged = case % 17 == 0;
                let reset = case % 19 == 0;
                if reset {
                    renderer.reset_transient();
                }
                let frame = serde_json::json!({"snapshot":snapshot,"status":status,"duration":duration,"privileged":privileged,"reset":reset}).to_string();
                let mut exchange = || {
                    writeln!(input, "{frame}").unwrap();
                    input.flush().unwrap();
                    let mut line = String::new();
                    assert!(output.read_line(&mut line).unwrap() > 0);
                    serde_json::from_str::<serde_json::Value>(&line).unwrap()
                };
                let mut actual = if case % 2 == 0 {
                    Some(exchange())
                } else {
                    None
                };
                let before = Instant::now();
                let expected = renderer.render(&snapshot, status, duration, privileged);
                let rust_ns = before.elapsed().as_nanos();
                let before = Instant::now();
                let rust_empty_ns = before.elapsed().as_nanos();
                if actual.is_none() {
                    actual = Some(exchange());
                }
                let actual = actual.unwrap();
                assert_eq!(
                    (actual[0].as_str().unwrap(), actual[1].as_str().unwrap()),
                    (expected.0.as_str(), expected.1.as_str()),
                    "theme {name}, environment {environment}, case {case}"
                );
                if !benchmark || case > 0 {
                    records.push(serde_json::json!({"theme":name,"environment":environment,"case":case,"c_first":case % 2 == 0,"rust_ns":rust_ns,"c_ns":actual[2],"rust_empty_ns":rust_empty_ns,"c_empty_ns":actual[3],"passed":true}));
                }
            }
            drop(input);
            assert!(child.wait().unwrap().success());
        }
    }
    std::fs::write(output_path, serde_json::to_vec_pretty(&records).unwrap()).unwrap();
}
