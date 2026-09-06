use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::os::unix::fs::{MetadataExt as _, OpenOptionsExt as _, PermissionsExt as _};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};
use wsh::{BundleStatus, bundle_manifest_for_profile};

const TRACE_NAME: &str = "trace.jsonl";
const ZPROF_NAME: &str = "zprof.txt";
const METADATA_NAME: &str = "metadata.json";
const MAX_TRACE_BYTES: u64 = 8 * 1024 * 1024;
const MAX_TRACE_LINE_BYTES: usize = 64 * 1024;
const MAX_ZPROF_BYTES: u64 = 1024 * 1024;

pub struct Session {
    pub directory: PathBuf,
    pub trace: PathBuf,
    pub zprof: PathBuf,
    metadata: PathBuf,
    pub started_unix_us: u128,
}

#[derive(Serialize)]
struct ManagerEvent<'a> {
    schema_version: u32,
    source: &'static str,
    event: &'static str,
    elapsed_us: u128,
    wsh_version: &'a str,
    bundle_sha256: &'a str,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ProfileMetadata {
    schema_version: u32,
    bundle_root: PathBuf,
    bundle_sha256: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Event {
    schema_version: u32,
    source: String,
    event: String,
    elapsed_us: u64,
    #[serde(default)]
    generation: Option<u64>,
    #[serde(default)]
    duration_us: Option<u64>,
    #[serde(default)]
    render_duration_us: Option<u64>,
    #[serde(default)]
    response_write_duration_us: Option<u64>,
    #[serde(default)]
    repository_discovery_us: Option<u64>,
    #[serde(default)]
    git_process_us: Option<u64>,
    #[serde(default)]
    parse_duration_us: Option<u64>,
    #[serde(default)]
    child_processes: Option<u64>,
    #[serde(default)]
    rendered_bytes: Option<u64>,
    #[serde(default)]
    prompt_changed: Option<bool>,
    #[serde(default)]
    repaint_cause: Option<String>,
    #[serde(default)]
    theme: Option<String>,
    #[serde(default)]
    wsh_version: Option<String>,
    #[serde(default)]
    bundle_sha256: Option<String>,
    #[serde(default)]
    history_owner: Option<String>,
    #[serde(default)]
    autosuggestions_owner: Option<String>,
    #[serde(default)]
    syntax_owner: Option<String>,
}

pub fn create(state_root: &Path, functions: bool) -> Result<Session, String> {
    let profiles = state_root.join("profiles");
    secure_directory(state_root)?;
    secure_directory(&profiles)?;
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|_| "system clock is before the Unix epoch")?;
    let started_unix_us = now.as_micros();
    let process = std::process::id();
    for attempt in 0..100 {
        let directory = profiles.join(format!("{}-{process}-{attempt}", now.as_secs()));
        match fs::create_dir(&directory) {
            Ok(()) => {
                fs::set_permissions(&directory, fs::Permissions::from_mode(0o700)).map_err(
                    |error| format!("could not secure {}: {error}", directory.display()),
                )?;
                let trace = directory.join(TRACE_NAME);
                let zprof = directory.join(ZPROF_NAME);
                let metadata = directory.join(METADATA_NAME);
                create_private_file(&trace)?;
                create_private_file(&metadata)?;
                if functions {
                    create_private_file(&zprof)?;
                }
                return Ok(Session {
                    directory,
                    trace,
                    zprof,
                    metadata,
                    started_unix_us,
                });
            }
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(error) => {
                return Err(format!("could not create profile directory: {error}"));
            }
        }
    }
    Err("could not allocate a private profile directory".into())
}

fn secure_directory(path: &Path) -> Result<(), String> {
    fs::create_dir_all(path)
        .map_err(|error| format!("could not create {}: {error}", path.display()))?;
    let metadata = fs::symlink_metadata(path)
        .map_err(|error| format!("could not inspect {}: {error}", path.display()))?;
    if !metadata.file_type().is_dir() || metadata.file_type().is_symlink() {
        return Err(format!(
            "profile path is not a real directory: {}",
            path.display()
        ));
    }
    fs::set_permissions(path, fs::Permissions::from_mode(0o700))
        .map_err(|error| format!("could not secure {}: {error}", path.display()))
}

fn create_private_file(path: &Path) -> Result<(), String> {
    OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)
        .map(|_| ())
        .map_err(|error| format!("could not create {}: {error}", path.display()))
}

pub fn record_manager_metadata(
    session: &Session,
    bundle_root: &Path,
    bundle_sha256: &str,
) -> Result<(), String> {
    let metadata = ProfileMetadata {
        schema_version: 1,
        bundle_root: bundle_root.to_path_buf(),
        bundle_sha256: bundle_sha256.to_owned(),
    };
    let metadata_file = OpenOptions::new()
        .write(true)
        .truncate(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_CLOEXEC)
        .open(&session.metadata)
        .map_err(|error| format!("could not open profile metadata: {error}"))?;
    serde_json::to_writer(metadata_file, &metadata)
        .map_err(|error| format!("could not encode profile metadata: {error}"))?;
    let elapsed_us = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|_| "system clock is before the Unix epoch")?
        .as_micros()
        .saturating_sub(session.started_unix_us);
    let event = ManagerEvent {
        schema_version: 1,
        source: "manager",
        event: "launch-ready",
        elapsed_us,
        wsh_version: env!("CARGO_PKG_VERSION"),
        bundle_sha256,
    };
    let mut file = OpenOptions::new()
        .append(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_CLOEXEC)
        .open(&session.trace)
        .map_err(|error| format!("could not open profile trace: {error}"))?;
    serde_json::to_writer(&mut file, &event)
        .map_err(|error| format!("could not encode profile metadata: {error}"))?;
    file.write_all(b"\n")
        .map_err(|error| format!("could not write profile metadata: {error}"))
}

pub fn started_seconds(session: &Session) -> String {
    format!(
        "{}.{:06}",
        session.started_unix_us / 1_000_000,
        session.started_unix_us % 1_000_000
    )
}

pub fn report(directory: &Path) -> Result<String, String> {
    let directory_metadata = fs::symlink_metadata(directory)
        .map_err(|error| format!("could not inspect {}: {error}", directory.display()))?;
    if !directory_metadata.file_type().is_dir()
        || directory_metadata.file_type().is_symlink()
        || directory_metadata.mode() & 0o077 != 0
    {
        return Err("profile directory is not private and real".into());
    }
    let trace_path = directory.join(TRACE_NAME);
    let zprof_path = directory.join(ZPROF_NAME);
    let profile_metadata = read_metadata(&directory.join(METADATA_NAME))?;
    let manifest = bundle_manifest_for_profile(
        &profile_metadata.bundle_root,
        &profile_metadata.bundle_sha256,
    )?;
    let events = read_events(&trace_path)?;
    let metadata = events
        .iter()
        .find(|event| event.source == "manager" && event.event == "launch-ready")
        .ok_or_else(|| "profile is missing manager build metadata".to_owned())?;
    if required(&metadata.bundle_sha256, "bundle digest")? != profile_metadata.bundle_sha256 {
        return Err("profile bundle identities disagree".into());
    }

    let mut output = String::from("Wsh profile\n");
    output.push_str(&format!(
        "Build: wsh {}, bundle {} ({})\n",
        required(&metadata.wsh_version, "wsh version")?,
        manifest.release_id,
        match manifest.status {
            BundleStatus::Development => "development",
            BundleStatus::Release => "release",
        }
    ));
    output.push_str(&format!(
        "Zsh: {} at {}\n",
        manifest.zsh.version,
        short_revision(&manifest.zsh.source_revision)
    ));
    output.push_str(&format!(
        "Source: {}  Target: {}  Bundle: {}\n",
        short_revision(&manifest.rust.source_revision),
        manifest.target,
        short_revision(required(&metadata.bundle_sha256, "bundle digest")?)
    ));

    output.push_str("\nStartup\n");
    push_milestone(
        &mut output,
        "Wsh ZLE initialization hook",
        find(&events, "editor-ready"),
    );
    push_milestone(
        &mut output,
        "Launcher to Zsh startup",
        find(&events, "zsh-startup-enter"),
    );
    push_span(
        &mut output,
        "User .zshenv",
        &events,
        "user-zshenv-start",
        "user-zshenv-end",
    );
    push_span(
        &mut output,
        "User .zprofile",
        &events,
        "user-zprofile-start",
        "user-zprofile-end",
    );
    push_span(
        &mut output,
        "User .zshrc",
        &events,
        "user-zshrc-start",
        "user-zshrc-end",
    );
    push_span(
        &mut output,
        "User .zlogin",
        &events,
        "user-zlogin-start",
        "user-zlogin-end",
    );
    push_span(
        &mut output,
        "History substring search",
        &events,
        "history-start",
        "history-end",
    );
    push_span(
        &mut output,
        "Autosuggestions",
        &events,
        "autosuggestions-start",
        "autosuggestions-end",
    );
    push_span(
        &mut output,
        "Syntax highlighting",
        &events,
        "syntax-highlighting-start",
        "syntax-highlighting-end",
    );
    push_span(
        &mut output,
        "Wsh integration",
        &events,
        "integration-start",
        "integration-end",
    );
    push_span(
        &mut output,
        "Wsh first precmd hook",
        &events,
        "precmd-start",
        "precmd-end",
    );
    push_milestone(&mut output, "Runtime ready", find(&events, "runtime-ready"));

    output.push_str("\nInitial asynchronous prompt\n");
    let worker = events.iter().find(|event| {
        event.source == "runtime"
            && event.event == "worker-completed"
            && event.generation == Some(1)
    });
    push_duration(
        &mut output,
        "Repository discovery",
        worker.and_then(|event| event.repository_discovery_us),
    );
    push_duration(
        &mut output,
        "Git process",
        worker.and_then(|event| event.git_process_us),
    );
    push_duration(
        &mut output,
        "Git output parsing",
        worker.and_then(|event| event.parse_duration_us),
    );
    push_duration(
        &mut output,
        "Provider total",
        worker.and_then(|event| event.duration_us),
    );
    if let Some(count) = worker.and_then(|event| event.child_processes) {
        output.push_str(&format!("Child processes: {count}\n"));
    } else {
        output.push_str("Child processes: unavailable\n");
    }
    let snapshot = events.iter().find(|event| {
        event.source == "runtime"
            && event.event == "snapshot-published"
            && event.generation == Some(1)
    });
    push_duration(
        &mut output,
        "Prompt rendering",
        snapshot.and_then(|event| event.render_duration_us),
    );
    push_duration(
        &mut output,
        "Response write",
        snapshot.and_then(|event| event.response_write_duration_us),
    );
    if let Some(bytes) = snapshot.and_then(|event| event.rendered_bytes) {
        output.push_str(&format!("Rendered prompt bytes: {bytes}\n"));
    }
    if let Some(changed) = snapshot.and_then(|event| event.prompt_changed) {
        output.push_str(&format!("Prompt changed: {changed}\n"));
    }
    if let Some(cause) = snapshot.and_then(|event| event.repaint_cause.as_deref()) {
        output.push_str(&format!("Repaint cause: {cause}\n"));
    }
    push_milestone(&mut output, "Snapshot published", snapshot);
    push_milestone(
        &mut output,
        "Snapshot applied and repainted",
        events.iter().find(|event| {
            event.source == "zsh"
                && event.event == "snapshot-applied"
                && event.generation == Some(1)
        }),
    );

    if let Some(ownership) = find(&events, "builtin-ownership") {
        output.push_str("\nBuilt-in ownership\n");
        output.push_str(&format!(
            "History substring search: {}\nAutosuggestions: {}\nSyntax highlighting: {}\n",
            ownership.history_owner.as_deref().unwrap_or("unavailable"),
            ownership
                .autosuggestions_owner
                .as_deref()
                .unwrap_or("unavailable"),
            ownership.syntax_owner.as_deref().unwrap_or("unavailable")
        ));
    }
    if let Some(theme) = events.iter().find_map(|event| event.theme.as_deref()) {
        output.push_str(&format!("Theme: {theme}\n"));
    }

    let functions = read_zprof(&zprof_path)?;
    output.push_str("\nSlowest Zsh functions by self time\n");
    if functions.is_empty() {
        output.push_str("unavailable\n");
    } else {
        for function in functions.into_iter().take(8) {
            output.push_str(&format!("{:.3} ms  {}\n", function.self_ms, function.name));
        }
    }
    output.push_str(&format!("\nTrace: {}\n", directory.display()));
    Ok(output)
}

fn read_metadata(path: &Path) -> Result<ProfileMetadata, String> {
    let metadata = fs::symlink_metadata(path)
        .map_err(|error| format!("could not inspect {}: {error}", path.display()))?;
    if !metadata.file_type().is_file()
        || metadata.file_type().is_symlink()
        || metadata.len() > 4096
        || metadata.mode() & 0o077 != 0
    {
        return Err("profile metadata is not a bounded private regular file".into());
    }
    let file = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_CLOEXEC)
        .open(path)
        .map_err(|error| format!("could not open profile metadata: {error}"))?;
    let metadata: ProfileMetadata = serde_json::from_reader(file)
        .map_err(|error| format!("invalid profile metadata: {error}"))?;
    if metadata.schema_version != 1
        || metadata.bundle_sha256.len() != 64
        || !metadata
            .bundle_sha256
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
    {
        return Err("profile metadata is unsupported".into());
    }
    Ok(metadata)
}

fn required<'a>(value: &'a Option<String>, name: &str) -> Result<&'a str, String> {
    value
        .as_deref()
        .ok_or_else(|| format!("profile is missing {name}"))
}

fn short_revision(value: &str) -> &str {
    value.get(..12).unwrap_or(value)
}

fn find<'a>(events: &'a [Event], name: &str) -> Option<&'a Event> {
    events.iter().find(|event| event.event == name)
}

fn push_milestone(output: &mut String, label: &str, event: Option<&Event>) {
    match event {
        Some(event) => output.push_str(&format!(
            "{label}: {:.3} ms\n",
            event.elapsed_us as f64 / 1000.0
        )),
        None => output.push_str(&format!("{label}: unavailable\n")),
    }
}

fn push_span(output: &mut String, label: &str, events: &[Event], start: &str, end: &str) {
    let duration = find(events, start)
        .zip(find(events, end))
        .and_then(|(start, end)| end.elapsed_us.checked_sub(start.elapsed_us));
    push_duration(output, label, duration);
}

fn push_duration(output: &mut String, label: &str, duration_us: Option<u64>) {
    match duration_us {
        Some(value) => output.push_str(&format!("{label}: {:.3} ms\n", value as f64 / 1000.0)),
        None => output.push_str(&format!("{label}: unavailable\n")),
    }
}

fn read_events(path: &Path) -> Result<Vec<Event>, String> {
    let metadata = fs::symlink_metadata(path)
        .map_err(|error| format!("could not inspect {}: {error}", path.display()))?;
    if !metadata.file_type().is_file()
        || metadata.file_type().is_symlink()
        || metadata.len() > MAX_TRACE_BYTES
        || metadata.mode() & 0o077 != 0
    {
        return Err("profile trace is not a bounded regular file".into());
    }
    let mut events = Vec::new();
    let mut reader = BufReader::new(
        OpenOptions::new()
            .read(true)
            .custom_flags(libc::O_NOFOLLOW | libc::O_CLOEXEC)
            .open(path)
            .map_err(|error| format!("could not open profile trace: {error}"))?,
    );
    let mut line = Vec::new();
    loop {
        line.clear();
        let count = reader
            .read_until(b'\n', &mut line)
            .map_err(|error| format!("could not read profile trace: {error}"))?;
        if count == 0 {
            break;
        }
        if line.len() > MAX_TRACE_LINE_BYTES || !line.ends_with(b"\n") {
            return Err("profile trace contains an oversized or incomplete event".into());
        }
        let event: Event = serde_json::from_slice(&line)
            .map_err(|error| format!("invalid profile trace event: {error}"))?;
        if event.schema_version != 1
            || !matches!(event.source.as_str(), "manager" | "zsh" | "runtime")
            || event.event.is_empty()
            || event.event.len() > 64
            || !event
                .event
                .bytes()
                .all(|byte| byte.is_ascii_lowercase() || byte == b'-')
        {
            return Err("profile trace contains an unsupported event".into());
        }
        events.push(event);
    }
    if events.len() > 100_000 {
        return Err("profile trace contains too many events".into());
    }
    Ok(events)
}

#[derive(Debug)]
struct FunctionProfile {
    self_ms: f64,
    name: String,
}

fn read_zprof(path: &Path) -> Result<Vec<FunctionProfile>, String> {
    let metadata = match fs::symlink_metadata(path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(error) => return Err(format!("could not inspect {}: {error}", path.display())),
    };
    if !metadata.file_type().is_file()
        || metadata.file_type().is_symlink()
        || metadata.len() > MAX_ZPROF_BYTES
        || metadata.mode() & 0o077 != 0
    {
        return Err("Zsh function profile is not a bounded regular file".into());
    }
    let mut value = String::new();
    OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NOFOLLOW | libc::O_CLOEXEC)
        .open(path)
        .and_then(|mut file| std::io::Read::read_to_string(&mut file, &mut value))
        .map_err(|error| format!("could not read Zsh function profile: {error}"))?;
    let mut functions = Vec::new();
    for line in value.lines().skip(2) {
        if line.is_empty() || line.starts_with('-') {
            break;
        }
        let fields: Vec<_> = line.split_whitespace().collect();
        if fields.len() != 9 || !fields[0].ends_with(')') {
            continue;
        }
        let Ok(self_ms) = fields[5].parse::<f64>() else {
            continue;
        };
        functions.push(FunctionProfile {
            self_ms,
            name: fields[8].to_owned(),
        });
    }
    functions.sort_by(|left, right| right.self_ms.total_cmp(&left.self_ms));
    Ok(functions)
}

#[cfg(test)]
mod tests {
    use super::{create, read_events, read_zprof};
    use std::fs;
    use std::os::unix::fs::{MetadataExt as _, PermissionsExt as _};

    #[test]
    fn creates_private_profile_storage() {
        let root = tempfile::tempdir().unwrap();
        let session = create(&root.path().join("state"), false).unwrap();
        assert_eq!(
            fs::metadata(&session.directory).unwrap().mode() & 0o777,
            0o700
        );
        assert_eq!(fs::metadata(&session.trace).unwrap().mode() & 0o777, 0o600);
        assert!(!session.zprof.exists());
        assert_eq!(
            fs::metadata(&session.metadata).unwrap().mode() & 0o777,
            0o600
        );
    }

    #[test]
    fn rejects_unknown_and_incomplete_trace_events() {
        let root = tempfile::tempdir().unwrap();
        let trace = root.path().join("trace.jsonl");
        fs::write(
            &trace,
            b"{\"schema_version\":2,\"source\":\"zsh\",\"event\":\"ready\",\"elapsed_us\":1}\n",
        )
        .unwrap();
        assert!(read_events(&trace).is_err());
        fs::write(&trace, b"{}\n").unwrap();
        assert!(read_events(&trace).is_err());
    }

    #[test]
    fn reads_the_zprof_summary_only() {
        let root = tempfile::tempdir().unwrap();
        let zprof = root.path().join("zprof.txt");
        fs::write(
            &zprof,
            "num  calls                time                       self            name\n-----------------------------------------------------------------------------------\n 1)    2           3.00     1.50   75.00%      2.50     1.25   62.50%  slow\n 2)    1           1.00     1.00   25.00%      1.00     1.00   25.00%  fast\n\n-----------------------------------------------------------------------------------\n",
        )
        .unwrap();
        fs::set_permissions(&zprof, fs::Permissions::from_mode(0o600)).unwrap();
        let result = read_zprof(&zprof).unwrap();
        assert_eq!(result.len(), 2);
        assert_eq!(result[0].name, "slow");
        assert_eq!(result[0].self_ms, 2.5);
    }
}
