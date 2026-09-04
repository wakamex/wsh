use std::fs::{self, File, OpenOptions};
use std::io::Read;
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, ExitStatus, Stdio};
use std::thread;
use std::time::{Duration, Instant};

const REPORT_VERSION: &str = "wsh-doctor-v1";
const MAX_REPORT_BYTES: u64 = 4096;
const CHILD_TIMEOUT: Duration = Duration::from_secs(10);
const REPORT_COMMAND: &str = r#"
typeset _wsh_doctor_syntax_owner=${WSH_SYNTAX_HIGHLIGHTING_OWNER-unset}
if [[ $_wsh_doctor_syntax_owner == disabled && ${_WSH_SYNTAX_HIGHLIGHTING_LOAD:-0} == 1 ]]; then
  _wsh_doctor_syntax_owner=wsh
fi
builtin print -r -- $'wsh-doctor-v1\t'${WSH_HISTORY_SUBSTRING_SEARCH_OWNER-unset}$'\t'${WSH_HISTORY_SUBSTRING_SEARCH_REPLACED-unset}$'\t'${WSH_AUTOSUGGESTIONS_OWNER-unset}$'\t'${WSH_AUTOSUGGESTIONS_REPLACED-unset}$'\t'$_wsh_doctor_syntax_owner >| "$WSH_DOCTOR_REPORT"
"#;

pub struct Shell<'a> {
    pub executable: &'a Path,
    pub bundle_root: &'a Path,
    pub runtime: &'a Path,
    pub theme: &'a Path,
    pub zdotdir: &'a Path,
    pub user_zdotdir: Option<&'a std::ffi::OsStr>,
}

struct ReportFile {
    path: PathBuf,
}

impl ReportFile {
    fn create() -> Result<Self, String> {
        let process = std::process::id();
        for attempt in 0..100 {
            let path = std::env::temp_dir().join(format!("wsh-doctor-{process}-{attempt}.report"));
            match OpenOptions::new()
                .write(true)
                .create_new(true)
                .mode(0o600)
                .open(&path)
            {
                Ok(_) => return Ok(Self { path }),
                Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(error) => {
                    return Err(format!("could not create private doctor report: {error}"));
                }
            }
        }
        Err("could not allocate a private doctor report".into())
    }

    fn read(&self) -> Result<String, String> {
        let metadata = fs::metadata(&self.path)
            .map_err(|error| format!("could not inspect doctor report: {error}"))?;
        if !metadata.is_file() || metadata.len() > MAX_REPORT_BYTES {
            return Err("doctor report is not a bounded regular file".into());
        }
        let mut value = String::new();
        File::open(&self.path)
            .and_then(|mut file| file.read_to_string(&mut value))
            .map_err(|error| format!("could not read doctor report: {error}"))?;
        Ok(value)
    }
}

impl Drop for ReportFile {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.path);
    }
}

#[derive(Debug, PartialEq, Eq)]
struct Report<'a> {
    history_owner: &'a str,
    history_replaced: &'a str,
    autosuggestions_owner: &'a str,
    autosuggestions_replaced: &'a str,
    syntax_owner: &'a str,
}

fn parse_report(value: &str) -> Result<Report<'_>, String> {
    let fields: Vec<_> = value.trim_end_matches('\n').split('\t').collect();
    let [
        version,
        history_owner,
        history_replaced,
        autosuggestions_owner,
        autosuggestions_replaced,
        syntax_owner,
    ] = fields.as_slice()
    else {
        return Err("diagnostic shell returned a malformed doctor report".into());
    };
    if *version != REPORT_VERSION {
        return Err("diagnostic shell returned an unsupported doctor report".into());
    }
    Ok(Report {
        history_owner,
        history_replaced,
        autosuggestions_owner,
        autosuggestions_replaced,
        syntax_owner,
    })
}

fn finding(component: &str, owner: &str, replaced: &str) -> Result<Option<String>, String> {
    match (owner, replaced) {
        ("wsh", "1") | ("external-active", "0") | ("external-exact", "0") => Ok(Some(format!(
            "- {component}: an exact external copy is redundant. Remove its startup declaration; wsh supplies the tested copy."
        ))),
        ("external-unknown", "0") => Ok(Some(format!(
            "- {component}: a modified or unrecognized external implementation was preserved. No removal is suggested."
        ))),
        ("wsh", "0") | ("disabled", "0") => Ok(None),
        _ => Err("diagnostic shell returned inconsistent plugin ownership".into()),
    }
}

fn render_report(report: &Report<'_>) -> Result<String, String> {
    if report
        == &(Report {
            history_owner: "unset",
            history_replaced: "unset",
            autosuggestions_owner: "unset",
            autosuggestions_replaced: "unset",
            syntax_owner: "unset",
        })
    {
        return Ok(
            "Plugin compatibility: this bundle does not expose plugin ownership diagnostics."
                .into(),
        );
    }

    let mut findings = Vec::new();
    if let Some(value) = finding(
        "zsh-history-substring-search",
        report.history_owner,
        report.history_replaced,
    )? {
        findings.push(value);
    }
    if let Some(value) = finding(
        "zsh-autosuggestions",
        report.autosuggestions_owner,
        report.autosuggestions_replaced,
    )? {
        findings.push(value);
    }
    if let Some(value) = finding("zsh-syntax-highlighting", report.syntax_owner, "0")? {
        findings.push(value);
    }
    if findings.is_empty() {
        Ok(
            "Plugin compatibility: no redundant or unrecognized external implementations detected."
                .into(),
        )
    } else {
        Ok(format!("Plugin compatibility:\n{}", findings.join("\n")))
    }
}

fn wait_for_child(child: &mut Child, timeout: Duration) -> Result<ExitStatus, String> {
    let started = Instant::now();
    loop {
        if let Some(status) = child
            .try_wait()
            .map_err(|error| format!("could not wait for diagnostic shell: {error}"))?
        {
            return Ok(status);
        }
        if started.elapsed() >= timeout {
            let _ = child.kill();
            let _ = child.wait();
            return Err(format!(
                "diagnostic shell did not finish within {} seconds",
                timeout.as_secs()
            ));
        }
        thread::sleep(Duration::from_millis(10));
    }
}

pub fn run(shell: Shell<'_>) -> Result<(), String> {
    let report_file = ReportFile::create()?;
    let mut command = Command::new(shell.executable);
    command
        .arg("-d")
        .arg("-i")
        .arg("-c")
        .arg(REPORT_COMMAND)
        .env("WSH_BUNDLE_ROOT", shell.bundle_root)
        .env("WSH_RUNTIME", shell.runtime)
        .env("WSH_THEME", shell.theme)
        .env("ZDOTDIR", shell.zdotdir)
        .env("WSH_DOCTOR_REPORT", &report_file.path)
        .env_remove("WSH_STARTUP_BUNDLE_ZDOTDIR")
        .env_remove("WSH_STARTUP_RCS")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    if let Some(user_zdotdir) = shell.user_zdotdir {
        command.env("WSH_USER_ZDOTDIR", user_zdotdir);
    } else {
        command.env_remove("WSH_USER_ZDOTDIR");
    }

    let mut child = command
        .spawn()
        .map_err(|error| format!("could not start diagnostic shell: {error}"))?;
    let status = wait_for_child(&mut child, CHILD_TIMEOUT)?;
    if !status.success() {
        return Err(format!("diagnostic shell exited with {status}"));
    }

    let report = report_file.read()?;
    println!("{}", render_report(&parse_report(&report)?)?);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{parse_report, render_report, wait_for_child};
    use std::process::Command;
    use std::time::Duration;

    #[test]
    fn renders_only_supported_findings() {
        let report =
            parse_report("wsh-doctor-v1\twsh\t1\texternal-unknown\t0\texternal-exact\n").unwrap();
        let rendered = render_report(&report).unwrap();
        assert!(rendered.contains("zsh-history-substring-search: an exact external copy"));
        assert!(rendered.contains("zsh-autosuggestions: a modified or unrecognized"));
        assert!(rendered.contains("zsh-syntax-highlighting: an exact external copy"));
    }

    #[test]
    fn treats_missing_adapter_state_as_an_unsupported_bundle() {
        let report = parse_report("wsh-doctor-v1\tunset\tunset\tunset\tunset\tunset\n").unwrap();
        assert_eq!(
            render_report(&report).unwrap(),
            "Plugin compatibility: this bundle does not expose plugin ownership diagnostics."
        );
    }

    #[test]
    fn rejects_partial_or_inconsistent_reports() {
        assert!(parse_report("wsh-doctor-v1\twsh\t0\n").is_err());
        let report = parse_report("wsh-doctor-v1\twsh\t2\twsh\t0\twsh\n").unwrap();
        assert!(render_report(&report).is_err());
    }

    #[test]
    fn terminates_a_diagnostic_child_at_its_deadline() {
        let mut child = Command::new("sleep").arg("10").spawn().unwrap();
        assert_eq!(
            wait_for_child(&mut child, Duration::ZERO).unwrap_err(),
            "diagnostic shell did not finish within 0 seconds"
        );
        assert!(child.try_wait().unwrap().is_some());
    }
}
