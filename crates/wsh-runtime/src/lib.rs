use std::collections::HashSet;
use std::fs::OpenOptions;
use std::fs::{self, File};
use std::io::{BufRead, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{ChildStdout, Command, Stdio};
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver, SyncSender};
use std::thread;
use std::time::{Duration, Instant};

use flate2::read::ZlibDecoder;
use serde::{Deserialize, Serialize};

const MAX_THEME_BYTES: u64 = 64 * 1024;
const MAX_PROTOCOL_LINE_BYTES: usize = 64 * 1024;
const MAX_LITERAL_CHARS: usize = 128;
const MAX_GIT_OUTPUT_BYTES: u64 = 4 * 1024 * 1024;
const GIT_TIMEOUT: Duration = Duration::from_secs(2);
const GIT_POLL_INTERVAL: Duration = Duration::from_micros(100);
const MAX_PENDING_EVENTS: usize = 32;
const WORKER_STOP_TIMEOUT: Duration = Duration::from_millis(2500);
const MAX_TRACE_BYTES: u64 = 8 * 1024 * 1024;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct Theme {
    pub schema_version: u32,
    pub id: String,
    pub name: String,
    pub left: Vec<Component>,
    pub right: Vec<Component>,
    pub context: ContextComponent,
    pub cwd: CwdComponent,
    pub git: GitComponent,
    pub duration: DurationComponent,
    pub prompt_character: PromptCharacterComponent,
}

#[derive(Debug, Clone, Copy, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "kebab-case")]
pub enum Component {
    Context,
    Cwd,
    Git,
    Duration,
    PromptCharacter,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct ContextComponent {
    pub enabled: bool,
    pub show_local: bool,
    pub show_ssh: bool,
    pub prefix: String,
    pub separator: String,
    pub suffix: String,
    pub color: Color,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct CwdComponent {
    pub enabled: bool,
    pub style: CwdStyle,
    pub show_on_change: bool,
    pub max_length: usize,
    pub home_symbol: String,
    pub color: Color,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum CwdStyle {
    Full,
    Short,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct GitComponent {
    pub enabled: bool,
    pub compact: bool,
    pub hide_branches: Vec<String>,
    pub prefix: String,
    pub separator: String,
    pub color: Color,
    pub symbols: GitSymbols,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct GitSymbols {
    pub branch: String,
    pub detached: String,
    pub tag: String,
    pub clean: String,
    pub staged: String,
    pub modified: String,
    pub untracked: String,
    pub ahead: String,
    pub behind: String,
    pub diverged: String,
    pub rebase: String,
    pub merge: String,
    pub cherry_pick: String,
    pub revert: String,
    pub bisect: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct DurationComponent {
    pub enabled: bool,
    pub threshold_ms: u64,
    pub format: DurationFormat,
    pub prefix: String,
    pub suffix: String,
    pub color: Color,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum DurationFormat {
    Milliseconds,
    Human,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields, rename_all = "kebab-case")]
pub struct PromptCharacterComponent {
    pub enabled: bool,
    pub success: String,
    pub failure: String,
    pub privileged: String,
    pub success_color: Color,
    pub failure_color: Color,
    pub privileged_color: Color,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Color {
    Default,
    Black,
    Red,
    Green,
    Yellow,
    Blue,
    Magenta,
    Cyan,
    White,
    BrightBlack,
    BrightRed,
    BrightGreen,
    BrightYellow,
    BrightBlue,
    BrightMagenta,
    BrightCyan,
    BrightWhite,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "kebab-case", deny_unknown_fields)]
enum Request {
    Ping {
        version: u32,
        id: u64,
    },
    Refresh {
        version: u32,
        id: u64,
        generation: u64,
        cwd_hex: String,
        exit_status: i32,
        duration_ms: Option<u64>,
        privileged: bool,
        reset_transient: bool,
    },
    Cancel {
        version: u32,
        id: u64,
        generation: u64,
    },
    Shutdown {
        version: u32,
        id: u64,
    },
}

#[derive(Debug, Serialize, Clone, PartialEq, Eq)]
pub struct GitSnapshot {
    pub schema_version: u32,
    pub generation: u64,
    pub cwd_hex: String,
    pub found: bool,
    pub root_hex: Option<String>,
    pub branch: Option<String>,
    pub detached_sha: Option<String>,
    pub exact_tag: Option<String>,
    pub staged: bool,
    pub modified: bool,
    pub untracked: bool,
    pub ahead: u64,
    pub behind: u64,
    pub operation: Option<GitOperation>,
    pub worktree: bool,
}

#[derive(Debug, Serialize, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum GitOperation {
    Rebase,
    Merge,
    CherryPick,
    Revert,
    Bisect,
}

#[derive(Serialize)]
struct Ready<'a> {
    version: u32,
    #[serde(rename = "type")]
    message_type: &'static str,
    theme: &'a str,
}

#[derive(Serialize)]
struct Response<'a> {
    version: u32,
    #[serde(rename = "type")]
    message_type: &'a str,
    id: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<&'a str>,
}

#[derive(Serialize)]
struct SnapshotResponse<'a> {
    version: u32,
    #[serde(rename = "type")]
    message_type: &'static str,
    id: u64,
    generation: u64,
    prompt_hex: String,
    rprompt_hex: String,
    snapshot: &'a GitSnapshot,
}

enum Event {
    Request(Request),
    Malformed,
    InputError(String),
    End,
    Worker(WorkerResult),
}

struct RefreshRequest {
    id: u64,
    generation: u64,
    cwd: PathBuf,
    exit_status: i32,
    duration_ms: Option<u64>,
    privileged: bool,
    reset_transient: bool,
}

struct ActiveWorker {
    generation: u64,
    cancel: Arc<AtomicBool>,
}

struct WorkerResult {
    request: RefreshRequest,
    result: Result<GitSnapshot, String>,
    cancelled: bool,
    elapsed: Duration,
}

struct Renderer {
    theme: Theme,
    home: Option<PathBuf>,
    user: String,
    host: String,
    ssh: bool,
    last_cwd_hex: Option<String>,
    last_git_key: Option<String>,
}

struct RenderInput<'a> {
    snapshot: &'a GitSnapshot,
    cwd_changed: bool,
    git_changed: bool,
    exit_status: i32,
    duration_ms: Option<u64>,
    privileged: bool,
}

struct Trace {
    file: Option<File>,
    started: Instant,
    bytes: u64,
}

impl Trace {
    fn from_env() -> Result<Self, String> {
        let started = Instant::now();
        let Some(path) = std::env::var_os("WSH_TRACE_FILE").map(PathBuf::from) else {
            return Ok(Self {
                file: None,
                started,
                bytes: 0,
            });
        };
        Self::from_path(&path, started)
    }

    fn from_path(path: &Path, started: Instant) -> Result<Self, String> {
        if let Ok(metadata) = fs::symlink_metadata(path) {
            if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
                return Err("WSH_TRACE_FILE must be a regular file".into());
            }
            if metadata.len() >= MAX_TRACE_BYTES {
                return Err(format!(
                    "WSH_TRACE_FILE already exceeds {MAX_TRACE_BYTES} bytes"
                ));
            }
        }
        #[cfg(unix)]
        use std::os::unix::fs::{OpenOptionsExt as _, PermissionsExt as _};
        let mut options = OpenOptions::new();
        options.create(true).append(true);
        #[cfg(unix)]
        options
            .mode(0o600)
            .custom_flags(libc::O_NOFOLLOW | libc::O_CLOEXEC);
        let file = options
            .open(path)
            .map_err(|error| format!("could not open trace {}: {error}", path.display()))?;
        if !file
            .metadata()
            .map_err(|error| format!("could not inspect trace {}: {error}", path.display()))?
            .is_file()
        {
            return Err("WSH_TRACE_FILE must be a regular file".into());
        }
        #[cfg(unix)]
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))
            .map_err(|error| format!("could not secure trace {}: {error}", path.display()))?;
        let bytes = file.metadata().map(|metadata| metadata.len()).unwrap_or(0);
        Ok(Self {
            file: Some(file),
            started,
            bytes,
        })
    }

    fn record(
        &mut self,
        event: &str,
        generation: Option<u64>,
        fields: &[(&str, serde_json::Value)],
    ) -> Result<(), String> {
        let Some(file) = &mut self.file else {
            return Ok(());
        };
        let mut object = serde_json::Map::new();
        object.insert("schema_version".into(), serde_json::json!(1));
        object.insert("event".into(), serde_json::json!(event));
        object.insert(
            "elapsed_us".into(),
            serde_json::json!(self.started.elapsed().as_micros()),
        );
        if let Some(generation) = generation {
            object.insert("generation".into(), serde_json::json!(generation));
        }
        for (name, value) in fields {
            object.insert((*name).to_owned(), value.clone());
        }
        let mut line = serde_json::to_vec(&object)
            .map_err(|error| format!("could not encode trace event: {error}"))?;
        line.push(b'\n');
        if self.bytes + line.len() as u64 > MAX_TRACE_BYTES {
            return Ok(());
        }
        file.write_all(&line)
            .and_then(|()| file.flush())
            .map_err(|error| format!("could not write trace: {error}"))?;
        self.bytes += line.len() as u64;
        Ok(())
    }
}

pub fn load_theme(path: &Path) -> Result<Theme, String> {
    let metadata = fs::symlink_metadata(path)
        .map_err(|error| format!("could not inspect theme {}: {error}", path.display()))?;
    if !metadata.file_type().is_file() || metadata.file_type().is_symlink() {
        return Err("theme must be a regular file".into());
    }
    if metadata.len() > MAX_THEME_BYTES {
        return Err(format!("theme exceeds {MAX_THEME_BYTES} bytes"));
    }
    let source = fs::read_to_string(path)
        .map_err(|error| format!("could not read theme {}: {error}", path.display()))?;
    parse_theme(&source)
}

pub fn parse_theme(source: &str) -> Result<Theme, String> {
    let theme: Theme = toml::from_str(source).map_err(|error| format!("invalid theme: {error}"))?;
    validate_theme(&theme)?;
    Ok(theme)
}

pub fn serve<R: BufRead + Send + 'static, W: Write>(
    theme: Theme,
    input: R,
    mut output: W,
) -> Result<(), String> {
    let mut trace = Trace::from_env()?;
    write_json(
        &mut output,
        &Ready {
            version: 1,
            message_type: "ready",
            theme: &theme.id,
        },
    )?;
    trace.record("runtime-ready", None, &[])?;
    let (events_tx, events_rx) = mpsc::sync_channel(MAX_PENDING_EVENTS);
    spawn_reader(input, events_tx.clone());
    run_event_loop(theme, &mut output, events_tx, events_rx, trace)
}

fn run_event_loop<W: Write>(
    theme: Theme,
    output: &mut W,
    events_tx: SyncSender<Event>,
    events_rx: Receiver<Event>,
    mut trace: Trace,
) -> Result<(), String> {
    let mut renderer = Renderer::new(theme);
    let mut active: Option<ActiveWorker> = None;
    let mut pending: Option<RefreshRequest> = None;
    let mut latest_generation = 0;
    let mut cancelled_through = 0;
    let mut last_rendered: Option<(String, String)> = None;
    while let Ok(event) = events_rx.recv() {
        match event {
            Event::Request(Request::Ping { version: 1, id }) => write_json(
                output,
                &Response {
                    version: 1,
                    message_type: "pong",
                    id: Some(id),
                    error: None,
                },
            )?,
            Event::Request(Request::Refresh {
                version: 1,
                id,
                generation,
                cwd_hex,
                exit_status,
                duration_ms,
                privileged,
                reset_transient,
            }) => match decode_path(&cwd_hex) {
                Ok(cwd) => {
                    if generation <= latest_generation {
                        write_error(output, Some(id), "refresh generation is stale")?;
                        continue;
                    }
                    latest_generation = generation;
                    trace.record("refresh-received", Some(generation), &[])?;
                    let request = RefreshRequest {
                        id,
                        generation,
                        cwd,
                        exit_status,
                        duration_ms,
                        privileged,
                        reset_transient,
                    };
                    if let Some(worker) = &active {
                        worker.cancel.store(true, Ordering::Release);
                        pending = Some(request);
                        trace.record("worker-cancel-requested", Some(worker.generation), &[])?;
                    } else {
                        active = Some(spawn_git_worker(request, events_tx.clone()));
                    }
                }
                Err(error) => write_error(output, Some(id), &error)?,
            },
            Event::Request(Request::Cancel {
                version: 1,
                id,
                generation,
            }) => {
                cancelled_through = cancelled_through.max(generation);
                if let Some(worker) = &active
                    && worker.generation <= generation
                {
                    worker.cancel.store(true, Ordering::Release);
                }
                pending = None;
                trace.record("generation-cancelled", Some(generation), &[])?;
                write_json(
                    output,
                    &Response {
                        version: 1,
                        message_type: "cancelled",
                        id: Some(id),
                        error: None,
                    },
                )?;
            }
            Event::Request(Request::Shutdown { version: 1, id }) => {
                trace.record("shutdown-requested", None, &[])?;
                stop_worker(&mut active, &events_rx)?;
                write_json(
                    output,
                    &Response {
                        version: 1,
                        message_type: "stopping",
                        id: Some(id),
                        error: None,
                    },
                )?;
                trace.record("runtime-stopping", None, &[])?;
                return Ok(());
            }
            Event::Request(request) => {
                write_error(output, request_id(&request), "unsupported protocol version")?
            }
            Event::Malformed => write_error(output, None, "malformed request")?,
            Event::InputError(error) => return Err(error),
            Event::End => {
                stop_worker(&mut active, &events_rx)?;
                return Ok(());
            }
            Event::Worker(worker) => {
                let is_current = active
                    .as_ref()
                    .is_some_and(|item| item.generation == worker.request.generation);
                if is_current {
                    active = None;
                    let publish = should_publish_result(
                        worker.request.generation,
                        latest_generation,
                        cancelled_through,
                        worker.cancelled,
                    );
                    trace.record(
                        if worker.cancelled || !publish {
                            "worker-cancelled"
                        } else if worker.result.is_ok() {
                            "worker-completed"
                        } else {
                            "worker-failed"
                        },
                        Some(worker.request.generation),
                        &[("duration_us", serde_json::json!(worker.elapsed.as_micros()))],
                    )?;
                    if publish {
                        match worker.result {
                            Ok(snapshot) => {
                                if worker.request.reset_transient {
                                    renderer.reset_transient();
                                }
                                let (prompt, rprompt) = renderer.render(
                                    &snapshot,
                                    worker.request.exit_status,
                                    worker.request.duration_ms,
                                    worker.request.privileged,
                                );
                                let rendered_bytes = prompt.len() + rprompt.len();
                                let prompt_changed =
                                    last_rendered.as_ref().is_none_or(|(left, right)| {
                                        left != &prompt || right != &rprompt
                                    });
                                write_json(
                                    output,
                                    &SnapshotResponse {
                                        version: 1,
                                        message_type: "snapshot",
                                        id: worker.request.id,
                                        generation: worker.request.generation,
                                        prompt_hex: encode_hex(prompt.as_bytes()),
                                        rprompt_hex: encode_hex(rprompt.as_bytes()),
                                        snapshot: &snapshot,
                                    },
                                )?;
                                trace.record(
                                    "snapshot-published",
                                    Some(worker.request.generation),
                                    &[
                                        ("rendered_bytes", serde_json::json!(rendered_bytes)),
                                        ("prompt_changed", serde_json::json!(prompt_changed)),
                                        (
                                            "repaint_cause",
                                            if prompt_changed {
                                                serde_json::json!("git-snapshot")
                                            } else {
                                                serde_json::Value::Null
                                            },
                                        ),
                                    ],
                                )?;
                                last_rendered = Some((prompt, rprompt));
                            }
                            Err(error) => write_error(output, Some(worker.request.id), &error)?,
                        }
                    }
                    if let Some(request) = pending.take() {
                        active = Some(spawn_git_worker(request, events_tx.clone()));
                    }
                }
            }
        }
    }
    Ok(())
}

fn should_publish_result(
    generation: u64,
    latest_generation: u64,
    cancelled_through: u64,
    worker_observed_cancel: bool,
) -> bool {
    !worker_observed_cancel && generation == latest_generation && generation > cancelled_through
}

fn stop_worker(active: &mut Option<ActiveWorker>, events: &Receiver<Event>) -> Result<(), String> {
    let Some(worker) = active.take() else {
        return Ok(());
    };
    worker.cancel.store(true, Ordering::Release);
    let deadline = Instant::now() + WORKER_STOP_TIMEOUT;
    while let Some(remaining) = deadline.checked_duration_since(Instant::now()) {
        match events.recv_timeout(remaining) {
            Ok(Event::Worker(result)) if result.request.generation == worker.generation => {
                return Ok(());
            }
            Ok(_) => {}
            Err(mpsc::RecvTimeoutError::Timeout | mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }
    Err("Git worker did not stop within 2.5 seconds".into())
}

fn spawn_reader<R: BufRead + Send + 'static>(mut input: R, events: SyncSender<Event>) {
    thread::spawn(move || {
        loop {
            match read_line_bounded(&mut input, MAX_PROTOCOL_LINE_BYTES) {
                Ok(Some(line)) => {
                    let event = serde_json::from_slice::<Request>(&line)
                        .map(Event::Request)
                        .unwrap_or(Event::Malformed);
                    if events.send(event).is_err() {
                        break;
                    }
                }
                Ok(None) => {
                    let _ = events.send(Event::End);
                    break;
                }
                Err(error) => {
                    let _ = events.send(Event::InputError(error));
                    break;
                }
            }
        }
    });
}

fn spawn_git_worker(request: RefreshRequest, events: SyncSender<Event>) -> ActiveWorker {
    let cancel = Arc::new(AtomicBool::new(false));
    let worker_cancel = cancel.clone();
    let generation = request.generation;
    thread::spawn(move || {
        let started = Instant::now();
        let (result, cancelled) =
            collect_git_snapshot(&request.cwd, request.generation, &worker_cancel);
        let _ = events.send(Event::Worker(WorkerResult {
            request,
            result,
            cancelled,
            elapsed: started.elapsed(),
        }));
    });
    ActiveWorker { generation, cancel }
}

fn collect_git_snapshot(
    cwd: &Path,
    generation: u64,
    cancel: &AtomicBool,
) -> (Result<GitSnapshot, String>, bool) {
    collect_git_snapshot_with_command(cwd, generation, cancel, Path::new("git"))
}

fn collect_git_snapshot_with_command(
    cwd: &Path,
    generation: u64,
    cancel: &AtomicBool,
    git: &Path,
) -> (Result<GitSnapshot, String>, bool) {
    let Some(identity) = discover_repository(cwd) else {
        return (Ok(empty_snapshot(cwd, generation)), false);
    };
    let mut command = Command::new(git);
    command
        .current_dir(cwd)
        .env("GIT_OPTIONAL_LOCKS", "0")
        .args([
            "status",
            "--porcelain=v2",
            "--branch",
            "--untracked-files=normal",
            "--ignore-submodules=dirty",
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    #[cfg(target_os = "linux")]
    unsafe {
        use std::os::unix::process::CommandExt as _;
        command.pre_exec(|| {
            if libc::setpgid(0, 0) != 0 || libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL) != 0 {
                return Err(std::io::Error::last_os_error());
            }
            Ok(())
        });
    }
    let mut child = match command.spawn() {
        Ok(child) => child,
        Err(error) => return (Err(format!("could not start Git status: {error}")), false),
    };
    let stdout = child.stdout.take().expect("piped Git stdout");
    let reader = thread::spawn(move || read_git_output(stdout));
    let started = Instant::now();
    let mut cancelled = false;
    let status = loop {
        if cancel.load(Ordering::Acquire) || started.elapsed() >= GIT_TIMEOUT {
            cancelled = cancel.load(Ordering::Acquire);
            kill_git_child(&mut child);
            break child.wait();
        }
        match child.try_wait() {
            Ok(Some(status)) => break Ok(status),
            Ok(None) => thread::sleep(GIT_POLL_INTERVAL),
            Err(error) => break Err(error),
        }
    };
    let output = reader
        .join()
        .map_err(|_| "Git output reader panicked".to_owned())
        .and_then(|result| result);
    if cancelled {
        return (Err("Git request cancelled".into()), true);
    }
    match status {
        Ok(status) if status.success() => {}
        Ok(status) => return (Err(format!("Git status exited with {status}")), false),
        Err(error) => {
            return (
                Err(format!("could not wait for Git status: {error}")),
                false,
            );
        }
    }
    let output = match output {
        Ok(output) => output,
        Err(error) => return (Err(error), false),
    };
    (parse_git_status(cwd, generation, identity, &output), false)
}

fn kill_git_child(child: &mut std::process::Child) {
    #[cfg(target_os = "linux")]
    unsafe {
        if libc::kill(-(child.id() as i32), libc::SIGKILL) == 0 {
            return;
        }
    }
    let _ = child.kill();
}

fn empty_snapshot(cwd: &Path, generation: u64) -> GitSnapshot {
    GitSnapshot {
        schema_version: 1,
        generation,
        cwd_hex: encode_path(cwd),
        found: false,
        root_hex: None,
        branch: None,
        detached_sha: None,
        exact_tag: None,
        staged: false,
        modified: false,
        untracked: false,
        ahead: 0,
        behind: 0,
        operation: None,
        worktree: false,
    }
}

fn read_git_output(stdout: ChildStdout) -> Result<Vec<u8>, String> {
    let mut output = Vec::new();
    stdout
        .take(MAX_GIT_OUTPUT_BYTES + 1)
        .read_to_end(&mut output)
        .map_err(|error| format!("could not read Git status: {error}"))?;
    if output.len() as u64 > MAX_GIT_OUTPUT_BYTES {
        return Err(format!("Git status exceeds {MAX_GIT_OUTPUT_BYTES} bytes"));
    }
    Ok(output)
}

struct RepositoryIdentity {
    root: PathBuf,
    git_dir: PathBuf,
    common_git_dir: PathBuf,
    branch: Option<String>,
    head_oid: Option<String>,
}

fn discover_repository(cwd: &Path) -> Option<RepositoryIdentity> {
    let canonical = cwd.canonicalize().ok()?;
    for candidate in canonical.ancestors() {
        let dot_git = candidate.join(".git");
        let git_dir = if dot_git.is_dir() {
            dot_git
        } else if dot_git.is_file() {
            let source = fs::read_to_string(&dot_git).ok()?;
            let path = Path::new(source.trim().strip_prefix("gitdir: ")?);
            if path.is_absolute() {
                path.to_path_buf()
            } else {
                candidate.join(path)
            }
        } else {
            continue;
        };
        let common_git_dir = fs::read_to_string(git_dir.join("commondir"))
            .ok()
            .map(|source| git_dir.join(source.trim()))
            .unwrap_or_else(|| git_dir.clone());
        let head = fs::read_to_string(git_dir.join("HEAD")).ok()?;
        let head = head.trim();
        let (branch, head_oid) = if let Some(reference) = head.strip_prefix("ref: ") {
            (
                reference.strip_prefix("refs/heads/").map(str::to_owned),
                resolve_ref(&git_dir, &common_git_dir, reference),
            )
        } else {
            (None, Some(head.to_owned()))
        };
        return Some(RepositoryIdentity {
            root: candidate.to_path_buf(),
            git_dir,
            common_git_dir,
            branch,
            head_oid,
        });
    }
    None
}

fn resolve_ref(git_dir: &Path, common_git_dir: &Path, reference: &str) -> Option<String> {
    if let Ok(value) = fs::read_to_string(git_dir.join(reference)) {
        return Some(value.trim().to_owned());
    }
    if let Ok(value) = fs::read_to_string(common_git_dir.join(reference)) {
        return Some(value.trim().to_owned());
    }
    fs::read_to_string(common_git_dir.join("packed-refs"))
        .ok()?
        .lines()
        .find_map(|line| {
            let (oid, name) = line.split_once(' ')?;
            (name == reference).then(|| oid.to_owned())
        })
}

fn parse_git_status(
    cwd: &Path,
    generation: u64,
    identity: RepositoryIdentity,
    output: &[u8],
) -> Result<GitSnapshot, String> {
    let source =
        std::str::from_utf8(output).map_err(|_| "Git status output is not UTF-8".to_owned())?;
    let mut staged = false;
    let mut modified = false;
    let mut untracked = false;
    let mut ahead = 0;
    let mut behind = 0;
    for line in source.lines() {
        if let Some(value) = line.strip_prefix("# branch.ab ") {
            let mut fields = value.split_whitespace();
            ahead = fields
                .next()
                .and_then(|field| field.strip_prefix('+'))
                .and_then(|field| field.parse().ok())
                .unwrap_or(0);
            behind = fields
                .next()
                .and_then(|field| field.strip_prefix('-'))
                .and_then(|field| field.parse().ok())
                .unwrap_or(0);
        } else if line.starts_with("1 ") || line.starts_with("2 ") {
            let xy = line.split_whitespace().nth(1).unwrap_or("..").as_bytes();
            staged |= xy.first().is_some_and(|value| *value != b'.');
            modified |= xy.get(1).is_some_and(|value| *value != b'.');
        } else if line.starts_with("u ") {
            staged = true;
            modified = true;
        } else if line.starts_with("? ") {
            untracked = true;
        }
    }
    let exact_tag = identity
        .head_oid
        .as_deref()
        .and_then(|head| find_exact_tag(&identity.common_git_dir, head));
    let detached_sha = identity
        .branch
        .is_none()
        .then(|| {
            identity
                .head_oid
                .as_deref()
                .unwrap_or("")
                .chars()
                .take(7)
                .collect()
        })
        .filter(|value: &String| !value.is_empty());
    Ok(GitSnapshot {
        schema_version: 1,
        generation,
        cwd_hex: encode_path(cwd),
        found: true,
        root_hex: Some(encode_path(&identity.root)),
        branch: identity.branch,
        detached_sha,
        exact_tag,
        staged,
        modified,
        untracked,
        ahead,
        behind,
        operation: detect_operation(&identity.git_dir),
        worktree: true,
    })
}

fn detect_operation(git_dir: &Path) -> Option<GitOperation> {
    if git_dir.join("rebase-merge").is_dir() || git_dir.join("rebase-apply").is_dir() {
        Some(GitOperation::Rebase)
    } else if git_dir.join("MERGE_HEAD").exists() {
        Some(GitOperation::Merge)
    } else if git_dir.join("CHERRY_PICK_HEAD").exists() {
        Some(GitOperation::CherryPick)
    } else if git_dir.join("REVERT_HEAD").exists() {
        Some(GitOperation::Revert)
    } else if git_dir.join("BISECT_LOG").exists() {
        Some(GitOperation::Bisect)
    } else {
        None
    }
}

fn find_exact_tag(git_dir: &Path, head_oid: &str) -> Option<String> {
    let mut matches = Vec::new();
    let tags = git_dir.join("refs/tags");
    if tags.is_dir() {
        collect_loose_tags(git_dir, &tags, &tags, head_oid, &mut matches);
    }
    if let Ok(packed) = fs::read_to_string(git_dir.join("packed-refs")) {
        let mut pending: Option<(String, String)> = None;
        for line in packed.lines() {
            if let Some(peeled) = line.strip_prefix('^') {
                if let Some((name, oid)) = pending.take()
                    && (oid == head_oid || peeled == head_oid)
                {
                    matches.push(name);
                }
            } else if let Some((oid, reference)) = line.split_once(' ')
                && let Some(name) = reference.strip_prefix("refs/tags/")
            {
                if oid == head_oid {
                    matches.push(name.to_owned());
                }
                pending = Some((name.to_owned(), oid.to_owned()));
            }
        }
    }
    matches.sort();
    matches.into_iter().next()
}

fn collect_loose_tags(
    git_dir: &Path,
    root: &Path,
    directory: &Path,
    head_oid: &str,
    matches: &mut Vec<String>,
) {
    let Ok(entries) = fs::read_dir(directory) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect_loose_tags(git_dir, root, &path, head_oid, matches);
        } else if let Ok(value) = fs::read_to_string(&path) {
            let oid = value.trim();
            if (oid == head_oid || peel_tag_object(git_dir, oid).as_deref() == Some(head_oid))
                && let Ok(relative) = path.strip_prefix(root)
            {
                matches.push(relative.to_string_lossy().into_owned());
            }
        }
    }
}

fn peel_tag_object(git_dir: &Path, oid: &str) -> Option<String> {
    if oid.len() < 3 || !oid.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return None;
    }
    let file = File::open(git_dir.join("objects").join(&oid[..2]).join(&oid[2..])).ok()?;
    let mut decoder = ZlibDecoder::new(file);
    let mut object = Vec::new();
    Read::by_ref(&mut decoder)
        .take(1024 * 1024)
        .read_to_end(&mut object)
        .ok()?;
    let header_end = object.iter().position(|byte| *byte == 0)?;
    if !object[..header_end].starts_with(b"tag ") {
        return None;
    }
    std::str::from_utf8(&object[header_end + 1..])
        .ok()?
        .lines()
        .find_map(|line| line.strip_prefix("object ").map(str::to_owned))
}

impl Renderer {
    fn new(theme: Theme) -> Self {
        Self {
            theme,
            home: std::env::var_os("HOME").map(PathBuf::from),
            user: std::env::var("USER").unwrap_or_default(),
            host: std::env::var("HOST").unwrap_or_else(|_| "localhost".into()),
            ssh: std::env::var_os("SSH_CONNECTION").is_some()
                || std::env::var_os("SSH_TTY").is_some(),
            last_cwd_hex: None,
            last_git_key: None,
        }
    }

    fn reset_transient(&mut self) {
        self.last_cwd_hex = None;
        self.last_git_key = None;
    }

    fn render(
        &mut self,
        snapshot: &GitSnapshot,
        exit_status: i32,
        duration_ms: Option<u64>,
        privileged: bool,
    ) -> (String, String) {
        let cwd_changed = self.last_cwd_hex.as_deref() != Some(&snapshot.cwd_hex);
        let git_key = snapshot_git_key(snapshot);
        let git_changed = self.last_git_key.as_deref() != Some(&git_key);
        let input = RenderInput {
            snapshot,
            cwd_changed,
            git_changed,
            exit_status,
            duration_ms,
            privileged,
        };
        let left = self.render_layout(&self.theme.left, &input);
        let right = self.render_layout(&self.theme.right, &input);
        self.last_cwd_hex = Some(snapshot.cwd_hex.clone());
        self.last_git_key = Some(git_key);
        (left, right)
    }

    fn render_layout(&self, layout: &[Component], input: &RenderInput<'_>) -> String {
        let mut output = String::new();
        for component in layout {
            match component {
                Component::Context => self.render_context(&mut output),
                Component::Cwd => self.render_cwd(
                    &mut output,
                    &decode_display_path(&input.snapshot.cwd_hex),
                    input.cwd_changed,
                ),
                Component::Git => self.render_git(&mut output, input.snapshot, input.git_changed),
                Component::Duration => self.render_duration(&mut output, input.duration_ms),
                Component::PromptCharacter => {
                    self.render_prompt_character(&mut output, input.exit_status, input.privileged)
                }
            }
        }
        output
    }

    fn render_context(&self, output: &mut String) {
        let config = &self.theme.context;
        if !config.enabled || (!config.show_local && !self.ssh) || (!config.show_ssh && self.ssh) {
            return;
        }
        push_styled(
            output,
            &format!(
                "{}{}{}{}{}",
                escape_prompt(&config.prefix),
                escape_prompt(&self.user),
                escape_prompt(&config.separator),
                escape_prompt(&self.host),
                escape_prompt(&config.suffix)
            ),
            &config.color,
        );
    }

    fn render_cwd(&self, output: &mut String, cwd: &str, changed: bool) {
        let config = &self.theme.cwd;
        if !config.enabled || (config.show_on_change && !changed) {
            return;
        }
        let path = Path::new(cwd);
        let text = if self.home.as_deref() == Some(path) {
            config.home_symbol.clone()
        } else {
            match config.style {
                CwdStyle::Full => cwd.to_owned(),
                CwdStyle::Short => path
                    .file_name()
                    .map(|name| name.to_string_lossy().into_owned())
                    .unwrap_or_else(|| "/".into()),
            }
        };
        let text = truncate_left(&text, config.max_length);
        push_styled(output, &escape_prompt(&text), &config.color);
        output.push(' ');
    }

    fn render_git(&self, output: &mut String, snapshot: &GitSnapshot, changed: bool) {
        let config = &self.theme.git;
        if !config.enabled || !snapshot.found {
            return;
        }
        let mut parts = Vec::new();
        let label = if let Some(branch) = &snapshot.branch {
            (!config.hide_branches.contains(branch))
                .then(|| format!("{}{}", config.symbols.branch, branch))
        } else if let Some(tag) = &snapshot.exact_tag {
            Some(format!("{}{}", config.symbols.tag, tag))
        } else {
            snapshot
                .detached_sha
                .as_ref()
                .map(|sha| format!("{}{}", config.symbols.detached, sha))
        };
        if snapshot.staged {
            parts.push(config.symbols.staged.clone());
        }
        if snapshot.modified {
            parts.push(config.symbols.modified.clone());
        }
        if snapshot.untracked {
            parts.push(config.symbols.untracked.clone());
        }
        if snapshot.ahead > 0 && snapshot.behind > 0 {
            parts.push(config.symbols.diverged.clone());
        } else if snapshot.ahead > 0 {
            parts.push(config.symbols.ahead.clone());
        } else if snapshot.behind > 0 {
            parts.push(config.symbols.behind.clone());
        }
        if let Some(operation) = snapshot.operation {
            parts.push(
                match operation {
                    GitOperation::Rebase => &config.symbols.rebase,
                    GitOperation::Merge => &config.symbols.merge,
                    GitOperation::CherryPick => &config.symbols.cherry_pick,
                    GitOperation::Revert => &config.symbols.revert,
                    GitOperation::Bisect => &config.symbols.bisect,
                }
                .clone(),
            );
        }
        if config.compact {
            if parts.is_empty() {
                parts.push(if changed {
                    label.unwrap_or_else(|| config.symbols.clean.clone())
                } else {
                    config.symbols.clean.clone()
                });
            } else if changed
                && let Some(branch) = snapshot.branch.as_ref()
                && !config.hide_branches.contains(branch)
            {
                parts.insert(0, branch.clone());
            }
        } else if let Some(label) = label {
            parts.insert(0, label);
        }
        if parts.is_empty() {
            return;
        }
        let text = format!("{}{} ", config.prefix, parts.join(&config.separator));
        push_styled(output, &escape_prompt(&text), &config.color);
    }

    fn render_duration(&self, output: &mut String, duration_ms: Option<u64>) {
        let config = &self.theme.duration;
        let Some(duration) = duration_ms.filter(|value| *value >= config.threshold_ms) else {
            return;
        };
        let formatted = match config.format {
            DurationFormat::Milliseconds => format!("{duration}ms"),
            DurationFormat::Human => format_duration(duration),
        };
        push_styled(
            output,
            &escape_prompt(&format!("{}{}{}", config.prefix, formatted, config.suffix)),
            &config.color,
        );
    }

    fn render_prompt_character(&self, output: &mut String, exit_status: i32, privileged: bool) {
        let config = &self.theme.prompt_character;
        let (text, color) = if privileged {
            (&config.privileged, &config.privileged_color)
        } else if exit_status == 0 {
            (&config.success, &config.success_color)
        } else {
            (&config.failure, &config.failure_color)
        };
        push_styled(output, &escape_prompt(text), color);
        output.push(' ');
    }
}

fn escape_prompt(value: &str) -> String {
    let mut output = String::with_capacity(value.len());
    for character in value.chars() {
        match character {
            '%' => output.push_str("%%"),
            '$' => output.push_str("\\$"),
            '`' => output.push_str("\\`"),
            '\\' => output.push_str("\\\\"),
            character if character.is_control() => output.push('�'),
            character => output.push(character),
        }
    }
    output
}

fn snapshot_git_key(snapshot: &GitSnapshot) -> String {
    if !snapshot.found {
        return String::new();
    }
    format!(
        "{}:{}",
        snapshot.root_hex.as_deref().unwrap_or_default(),
        snapshot
            .branch
            .as_deref()
            .or(snapshot.exact_tag.as_deref())
            .or(snapshot.detached_sha.as_deref())
            .unwrap_or_default()
    )
}

fn truncate_left(value: &str, max_length: usize) -> String {
    let length = value.chars().count();
    if max_length == 0 || length <= max_length {
        return value.to_owned();
    }
    let keep = max_length.saturating_sub(2);
    format!(
        "..{}",
        value.chars().skip(length - keep).collect::<String>()
    )
}

fn format_duration(duration_ms: u64) -> String {
    let mut remaining = duration_ms / 1000;
    let days = remaining / 86_400;
    remaining %= 86_400;
    let hours = remaining / 3_600;
    remaining %= 3_600;
    let minutes = remaining / 60;
    let seconds = remaining % 60;
    let mut parts = Vec::new();
    if days > 0 {
        parts.push(format!("{days}d"));
    }
    if hours > 0 {
        parts.push(format!("{hours}h"));
    }
    if minutes > 0 {
        parts.push(format!("{minutes}m"));
    }
    if seconds > 0 || parts.is_empty() {
        parts.push(format!("{seconds}s"));
    }
    parts.join(" ")
}

fn push_styled(output: &mut String, value: &str, color: &Color) {
    if matches!(color, Color::Default) {
        output.push_str(value);
    } else {
        output.push_str("%F{");
        output.push_str(color_name(color));
        output.push('}');
        output.push_str(value);
        output.push_str("%f");
    }
}

fn color_name(color: &Color) -> &'static str {
    match color {
        Color::Default => "default",
        Color::Black => "black",
        Color::Red => "red",
        Color::Green => "green",
        Color::Yellow => "yellow",
        Color::Blue => "blue",
        Color::Magenta => "magenta",
        Color::Cyan => "cyan",
        Color::White => "white",
        Color::BrightBlack => "8",
        Color::BrightRed => "9",
        Color::BrightGreen => "10",
        Color::BrightYellow => "11",
        Color::BrightBlue => "12",
        Color::BrightMagenta => "13",
        Color::BrightCyan => "14",
        Color::BrightWhite => "15",
    }
}

fn validate_theme(theme: &Theme) -> Result<(), String> {
    if theme.schema_version != 1 {
        return Err(format!(
            "unsupported theme schema version: {}",
            theme.schema_version
        ));
    }
    validate_identifier("id", &theme.id)?;
    validate_literal("name", &theme.name)?;
    let mut components = HashSet::new();
    for component in theme.left.iter().chain(&theme.right) {
        if !components.insert(*component) {
            return Err(format!("component appears more than once: {component:?}"));
        }
    }
    if !components.contains(&Component::PromptCharacter) || !theme.prompt_character.enabled {
        return Err("prompt-character must be enabled and present in the layout".into());
    }
    for (component, enabled) in [
        (Component::Context, theme.context.enabled),
        (Component::Cwd, theme.cwd.enabled),
        (Component::Git, theme.git.enabled),
        (Component::Duration, theme.duration.enabled),
        (Component::PromptCharacter, theme.prompt_character.enabled),
    ] {
        if components.contains(&component) != enabled {
            return Err(format!(
                "layout and enabled state disagree for {component:?}"
            ));
        }
    }
    if theme.git.hide_branches.len() > 16 {
        return Err("git.hide-branches exceeds 16 entries".into());
    }
    if theme.cwd.max_length > 4096 {
        return Err("cwd.max-length exceeds 4096 characters".into());
    }
    for branch in &theme.git.hide_branches {
        validate_literal("git.hide-branches", branch)?;
    }
    for (name, literal) in literals(theme) {
        validate_literal(name, literal)?;
    }
    Ok(())
}

fn literals(theme: &Theme) -> Vec<(&'static str, &str)> {
    vec![
        ("context.separator", &theme.context.separator),
        ("context.prefix", &theme.context.prefix),
        ("context.suffix", &theme.context.suffix),
        ("cwd.home-symbol", &theme.cwd.home_symbol),
        ("git.prefix", &theme.git.prefix),
        ("git.separator", &theme.git.separator),
        ("git.symbols.branch", &theme.git.symbols.branch),
        ("git.symbols.detached", &theme.git.symbols.detached),
        ("git.symbols.tag", &theme.git.symbols.tag),
        ("git.symbols.clean", &theme.git.symbols.clean),
        ("git.symbols.staged", &theme.git.symbols.staged),
        ("git.symbols.modified", &theme.git.symbols.modified),
        ("git.symbols.untracked", &theme.git.symbols.untracked),
        ("git.symbols.ahead", &theme.git.symbols.ahead),
        ("git.symbols.behind", &theme.git.symbols.behind),
        ("git.symbols.diverged", &theme.git.symbols.diverged),
        ("git.symbols.rebase", &theme.git.symbols.rebase),
        ("git.symbols.merge", &theme.git.symbols.merge),
        ("git.symbols.cherry-pick", &theme.git.symbols.cherry_pick),
        ("git.symbols.revert", &theme.git.symbols.revert),
        ("git.symbols.bisect", &theme.git.symbols.bisect),
        ("duration.prefix", &theme.duration.prefix),
        ("duration.suffix", &theme.duration.suffix),
        ("prompt-character.success", &theme.prompt_character.success),
        ("prompt-character.failure", &theme.prompt_character.failure),
        (
            "prompt-character.privileged",
            &theme.prompt_character.privileged,
        ),
    ]
}

fn validate_identifier(name: &str, value: &str) -> Result<(), String> {
    if value.is_empty()
        || value.len() > 64
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
    {
        return Err(format!("{name} is not a lowercase ASCII identifier"));
    }
    Ok(())
}

fn validate_literal(name: &str, value: &str) -> Result<(), String> {
    if value.chars().count() > MAX_LITERAL_CHARS || value.chars().any(char::is_control) {
        return Err(format!("{name} is too long or contains control characters"));
    }
    Ok(())
}

fn request_id(request: &Request) -> Option<u64> {
    Some(match request {
        Request::Ping { id, .. }
        | Request::Refresh { id, .. }
        | Request::Cancel { id, .. }
        | Request::Shutdown { id, .. } => *id,
    })
}

fn decode_path(hex: &str) -> Result<PathBuf, String> {
    if hex.len() > 8192 || !hex.len().is_multiple_of(2) {
        return Err("cwd_hex is malformed or too long".into());
    }
    let mut bytes = Vec::with_capacity(hex.len() / 2);
    for pair in hex.as_bytes().chunks_exact(2) {
        let pair = std::str::from_utf8(pair).map_err(|_| "cwd_hex is malformed")?;
        bytes.push(u8::from_str_radix(pair, 16).map_err(|_| "cwd_hex is malformed")?);
    }
    #[cfg(unix)]
    let path = {
        use std::ffi::OsString;
        use std::os::unix::ffi::OsStringExt as _;
        PathBuf::from(OsString::from_vec(bytes))
    };
    #[cfg(not(unix))]
    let path = PathBuf::from(String::from_utf8(bytes).map_err(|_| "cwd is not UTF-8")?);
    if !path.is_absolute() {
        return Err("cwd must be an absolute path".into());
    }
    Ok(path)
}

fn encode_path(path: &Path) -> String {
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStrExt as _;
        encode_hex(path.as_os_str().as_bytes())
    }
    #[cfg(not(unix))]
    {
        encode_hex(path.as_os_str().to_string_lossy().as_bytes())
    }
}

fn decode_display_path(hex: &str) -> String {
    let bytes = hex
        .as_bytes()
        .chunks_exact(2)
        .filter_map(|pair| std::str::from_utf8(pair).ok())
        .filter_map(|pair| u8::from_str_radix(pair, 16).ok())
        .collect::<Vec<_>>();
    String::from_utf8_lossy(&bytes).into_owned()
}

fn encode_hex(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        use std::fmt::Write as _;
        let _ = write!(output, "{byte:02x}");
    }
    output
}

fn read_line_bounded<R: BufRead>(reader: &mut R, limit: usize) -> Result<Option<Vec<u8>>, String> {
    let mut line = Vec::new();
    loop {
        let available = reader
            .fill_buf()
            .map_err(|error| format!("could not read request: {error}"))?;
        if available.is_empty() {
            return if line.is_empty() {
                Ok(None)
            } else {
                Ok(Some(line))
            };
        }
        let count = available
            .iter()
            .position(|byte| *byte == b'\n')
            .map_or(available.len(), |position| position + 1);
        if line.len() + count > limit {
            return Err(format!("protocol line exceeds {limit} bytes"));
        }
        line.extend_from_slice(&available[..count]);
        reader.consume(count);
        if line.last() == Some(&b'\n') {
            line.pop();
            if line.last() == Some(&b'\r') {
                line.pop();
            }
            return Ok(Some(line));
        }
    }
}

fn write_error<W: Write>(writer: &mut W, id: Option<u64>, error: &str) -> Result<(), String> {
    write_json(
        writer,
        &Response {
            version: 1,
            message_type: "error",
            id,
            error: Some(error),
        },
    )
}

fn write_json<W: Write, T: Serialize>(writer: &mut W, value: &T) -> Result<(), String> {
    serde_json::to_writer(&mut *writer, value)
        .map_err(|error| format!("could not encode response: {error}"))?;
    writer
        .write_all(b"\n")
        .map_err(|error| format!("could not write response: {error}"))?;
    writer
        .flush()
        .map_err(|error| format!("could not flush response: {error}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;
    use std::sync::Mutex;

    const VALID_THEME: &str = include_str!("../../../themes/minimal.toml");
    const WAKAMEX_THEME: &str = include_str!("../../../themes/wakamex.toml");

    #[test]
    fn parses_the_bundled_minimal_theme() {
        assert_eq!(parse_theme(VALID_THEME).unwrap().id, "minimal");
        assert_eq!(parse_theme(WAKAMEX_THEME).unwrap().id, "wakamex");
    }

    #[test]
    fn rejects_unknown_theme_fields() {
        let source = VALID_THEME.replace(
            "schema-version = 1",
            "schema-version = 1\nshell = \"echo unsafe\"",
        );
        assert!(parse_theme(&source).is_err());
    }

    #[test]
    fn rejects_control_characters_in_literals() {
        let source = VALID_THEME.replace("success = \"%\"", "success = \"\\u001b[31m%\"");
        assert!(parse_theme(&source).is_err());
    }

    #[test]
    fn escapes_zsh_prompt_substitution_and_terminal_controls() {
        assert_eq!(
            escape_prompt("$(touch owned) `touch owned` \\ %\nnext"),
            "\\$(touch owned) \\`touch owned\\` \\\\ %%�next"
        );
    }

    #[cfg(unix)]
    #[test]
    fn trace_is_versioned_bounded_private_and_rejects_symlinks() {
        use std::os::unix::fs::{MetadataExt as _, symlink};

        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("trace.jsonl");
        let mut trace = Trace::from_path(&path, Instant::now()).unwrap();
        trace
            .record(
                "snapshot-published",
                Some(7),
                &[("rendered_bytes", serde_json::json!(42))],
            )
            .unwrap();
        drop(trace);
        let value: serde_json::Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(value["schema_version"], 1);
        assert_eq!(value["generation"], 7);
        assert!(value.get("cwd").is_none());
        assert_eq!(fs::metadata(&path).unwrap().mode() & 0o777, 0o600);
        let link = directory.path().join("trace-link");
        symlink(&path, &link).unwrap();
        assert!(Trace::from_path(&link, Instant::now()).is_err());
    }

    #[test]
    fn wakamex_port_preserves_changed_only_and_compact_state() {
        let mut renderer = Renderer::new(parse_theme(WAKAMEX_THEME).unwrap());
        let mut snapshot = sample_snapshot();
        let (first, _) = renderer.render(&snapshot, 0, None, false);
        assert!(first.contains("/tmp/project"));
        assert!(first.contains('±'));
        let (second, _) = renderer.render(&snapshot, 0, None, false);
        assert!(!second.contains("/tmp/project"));
        assert!(second.contains('±'));
        snapshot.modified = true;
        snapshot.ahead = 1;
        snapshot.behind = 1;
        snapshot.operation = Some(GitOperation::Rebase);
        let (dirty, _) = renderer.render(&snapshot, 1, Some(61_000), false);
        assert!(dirty.contains('!'));
        assert!(dirty.contains('⇅'));
        assert!(dirty.contains(">R>"));
        assert!(dirty.contains("1m 1s"));
        renderer.reset_transient();
        let (reset, _) = renderer.render(&snapshot, 0, None, false);
        assert!(reset.contains("/tmp/project"));
    }

    #[cfg(unix)]
    #[test]
    fn publishes_one_complete_snapshot_and_rejects_stale_generations() {
        use std::os::unix::net::UnixStream;

        let directory = make_repository();
        let (mut client, server) = UnixStream::pair().unwrap();
        let bytes = Arc::new(Mutex::new(Vec::new()));
        let writer = SharedWriter(bytes.clone());
        let runtime = thread::spawn(move || {
            serve(
                parse_theme(VALID_THEME).unwrap(),
                std::io::BufReader::new(server),
                writer,
            )
            .unwrap();
        });
        let cwd_hex = encode_path(directory.path());
        writeln!(
            client,
            "{{\"type\":\"refresh\",\"version\":1,\"id\":1,\"generation\":1,\"cwd_hex\":\"{cwd_hex}\",\"exit_status\":0,\"duration_ms\":null,\"privileged\":false,\"reset_transient\":false}}"
        )
        .unwrap();
        let deadline = Instant::now() + Duration::from_secs(1);
        while !String::from_utf8_lossy(&bytes.lock().unwrap()).contains("\"type\":\"snapshot\"")
            && Instant::now() < deadline
        {
            thread::sleep(Duration::from_millis(1));
        }
        writeln!(
            client,
            "{{\"type\":\"refresh\",\"version\":1,\"id\":2,\"generation\":1,\"cwd_hex\":\"{cwd_hex}\",\"exit_status\":0,\"duration_ms\":null,\"privileged\":false,\"reset_transient\":false}}"
        )
        .unwrap();
        writeln!(client, "{{\"type\":\"shutdown\",\"version\":1,\"id\":3}}").unwrap();
        runtime.join().unwrap();
        let output = String::from_utf8(bytes.lock().unwrap().clone()).unwrap();
        assert_eq!(output.matches("\"type\":\"snapshot\"").count(), 1);
        assert!(output.contains("\"schema_version\":1"));
        assert!(output.contains(&format!("\"cwd_hex\":\"{cwd_hex}\"")));
        assert!(output.contains("refresh generation is stale"));
        assert!(output.contains("\"type\":\"stopping\",\"id\":3"));
    }

    #[cfg(unix)]
    #[test]
    fn cancellation_kills_the_git_process_group() {
        use std::os::unix::fs::PermissionsExt as _;

        let directory = make_repository();
        let script = directory.path().join("slow-git");
        let child_pid = directory.path().join("child.pid");
        fs::write(
            &script,
            format!(
                "#!/bin/sh\nsleep 10 &\necho $! > {}\nwait\n",
                child_pid.display()
            ),
        )
        .unwrap();
        fs::set_permissions(&script, fs::Permissions::from_mode(0o755)).unwrap();
        let cancel = Arc::new(AtomicBool::new(false));
        let worker_cancel = cancel.clone();
        let cwd = directory.path().to_path_buf();
        let worker = thread::spawn(move || {
            collect_git_snapshot_with_command(&cwd, 1, &worker_cancel, &script)
        });
        let deadline = Instant::now() + Duration::from_secs(1);
        while !child_pid.exists() && Instant::now() < deadline {
            thread::sleep(Duration::from_millis(1));
        }
        let pid: i32 = fs::read_to_string(&child_pid)
            .unwrap()
            .trim()
            .parse()
            .unwrap();
        cancel.store(true, Ordering::Release);
        let (_, cancelled) = worker.join().unwrap();
        assert!(cancelled);
        let deadline = Instant::now() + Duration::from_secs(1);
        let mut gone = false;
        while Instant::now() < deadline {
            gone = unsafe { libc::kill(pid, 0) } != 0;
            if gone {
                break;
            }
            thread::sleep(Duration::from_millis(1));
        }
        assert!(gone, "cancelled Git descendant {pid} survived");
    }

    #[test]
    fn serves_versioned_ping_and_shutdown() {
        let input = Cursor::new(b"{\"type\":\"ping\",\"version\":1,\"id\":7}\n{\"type\":\"shutdown\",\"version\":1,\"id\":8}\n");
        let mut output = Vec::new();
        serve(parse_theme(VALID_THEME).unwrap(), input, &mut output).unwrap();
        let output = String::from_utf8(output).unwrap();
        assert!(output.contains("\"type\":\"ready\""));
        assert!(output.contains("\"type\":\"pong\",\"id\":7"));
        assert!(output.contains("\"type\":\"stopping\",\"id\":8"));
    }

    #[test]
    fn final_generation_check_rejects_completed_but_superseded_work() {
        assert!(should_publish_result(2, 2, 1, false));
        assert!(!should_publish_result(1, 2, 0, false));
        assert!(!should_publish_result(2, 2, 2, false));
        assert!(!should_publish_result(2, 2, 1, true));
    }

    #[test]
    fn rejects_oversized_protocol_lines_without_unbounded_read() {
        let mut input = Cursor::new(vec![b'x'; MAX_PROTOCOL_LINE_BYTES + 1]);
        assert!(read_line_bounded(&mut input, MAX_PROTOCOL_LINE_BYTES).is_err());
    }

    #[test]
    fn parses_real_git_status_and_exact_annotated_tag() {
        let directory = make_repository();
        run_git(directory.path(), &["tag", "-am", "release", "v1"]);
        let cancel = AtomicBool::new(false);
        let (snapshot, cancelled) = collect_git_snapshot(directory.path(), 1, &cancel);
        let snapshot = snapshot.unwrap();
        assert!(!cancelled);
        assert_eq!(snapshot.branch.as_deref(), Some("main"));
        assert!(!snapshot.staged && !snapshot.modified && !snapshot.untracked);
        fs::write(directory.path().join("tracked"), "dirty\n").unwrap();
        fs::write(directory.path().join("untracked"), "new\n").unwrap();
        let (snapshot, _) = collect_git_snapshot(directory.path(), 2, &cancel);
        let snapshot = snapshot.unwrap();
        assert!(snapshot.modified && snapshot.untracked);
        run_git(directory.path(), &["checkout", "-q", "--detach", "HEAD"]);
        let (snapshot, _) = collect_git_snapshot(directory.path(), 3, &cancel);
        let snapshot = snapshot.unwrap();
        assert_eq!(snapshot.exact_tag.as_deref(), Some("v1"));
        assert!(snapshot.detached_sha.is_some());
    }

    #[test]
    fn resolves_common_refs_and_tags_in_a_linked_worktree() {
        let directory = make_repository();
        run_git(directory.path(), &["tag", "-am", "release", "v1"]);
        let worktrees = tempfile::tempdir().unwrap();
        let linked = worktrees.path().join("linked");
        run_git(
            directory.path(),
            &[
                "worktree",
                "add",
                "-q",
                "--detach",
                linked.to_str().unwrap(),
            ],
        );
        let cancel = AtomicBool::new(false);
        let (snapshot, cancelled) = collect_git_snapshot(&linked, 1, &cancel);
        let snapshot = snapshot.unwrap();
        assert!(!cancelled);
        assert!(snapshot.worktree);
        assert_eq!(snapshot.exact_tag.as_deref(), Some("v1"));
        assert!(snapshot.detached_sha.is_some());
    }

    #[test]
    fn parses_ahead_and_behind_from_a_diverged_upstream() {
        let directory = make_repository();
        run_git(directory.path(), &["switch", "-qc", "upstream"]);
        fs::write(directory.path().join("upstream"), "upstream\n").unwrap();
        run_git(directory.path(), &["add", "upstream"]);
        run_git(directory.path(), &["commit", "-qm", "upstream"]);
        run_git(directory.path(), &["switch", "-q", "main"]);
        fs::write(directory.path().join("local"), "local\n").unwrap();
        run_git(directory.path(), &["add", "local"]);
        run_git(directory.path(), &["commit", "-qm", "local"]);
        run_git(directory.path(), &["config", "branch.main.remote", "."]);
        run_git(
            directory.path(),
            &["config", "branch.main.merge", "refs/heads/upstream"],
        );
        let cancel = AtomicBool::new(false);
        let (snapshot, cancelled) = collect_git_snapshot(directory.path(), 1, &cancel);
        let snapshot = snapshot.unwrap();
        assert!(!cancelled);
        assert_eq!((snapshot.ahead, snapshot.behind), (1, 1));
    }

    #[test]
    fn detects_each_repository_operation_marker() {
        let directory = tempfile::tempdir().unwrap();
        let git_dir = directory.path();
        for (path, operation, is_directory) in [
            ("rebase-merge", GitOperation::Rebase, true),
            ("MERGE_HEAD", GitOperation::Merge, false),
            ("CHERRY_PICK_HEAD", GitOperation::CherryPick, false),
            ("REVERT_HEAD", GitOperation::Revert, false),
            ("BISECT_LOG", GitOperation::Bisect, false),
        ] {
            let marker = git_dir.join(path);
            if is_directory {
                fs::create_dir(&marker).unwrap();
            } else {
                fs::write(&marker, "marker").unwrap();
            }
            assert_eq!(detect_operation(git_dir), Some(operation));
            if is_directory {
                fs::remove_dir(&marker).unwrap();
            } else {
                fs::remove_file(&marker).unwrap();
            }
        }
        assert_eq!(detect_operation(git_dir), None);
    }

    fn run_git(directory: &Path, args: &[&str]) {
        assert!(
            Command::new("git")
                .current_dir(directory)
                .args(args)
                .status()
                .unwrap()
                .success(),
            "git {args:?} failed"
        );
    }

    fn make_repository() -> tempfile::TempDir {
        let directory = tempfile::tempdir().unwrap();
        run_git(directory.path(), &["init", "-q", "-b", "main"]);
        run_git(directory.path(), &["config", "user.name", "wsh test"]);
        run_git(
            directory.path(),
            &["config", "user.email", "test@wsh.invalid"],
        );
        fs::write(directory.path().join("tracked"), "clean\n").unwrap();
        run_git(directory.path(), &["add", "tracked"]);
        run_git(directory.path(), &["commit", "-qm", "initial"]);
        directory
    }

    #[derive(Clone)]
    struct SharedWriter(Arc<Mutex<Vec<u8>>>);

    impl Write for SharedWriter {
        fn write(&mut self, buffer: &[u8]) -> std::io::Result<usize> {
            self.0.lock().unwrap().extend_from_slice(buffer);
            Ok(buffer.len())
        }

        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }

    fn sample_snapshot() -> GitSnapshot {
        GitSnapshot {
            schema_version: 1,
            generation: 1,
            cwd_hex: encode_hex(b"/tmp/project"),
            found: true,
            root_hex: Some(encode_hex(b"/tmp/project")),
            branch: Some("main".into()),
            detached_sha: None,
            exact_tag: None,
            staged: false,
            modified: false,
            untracked: false,
            ahead: 0,
            behind: 0,
            operation: None,
            worktree: true,
        }
    }
}
