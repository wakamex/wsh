use super::*;
#[cfg(all(test, feature = "native-git"))]
#[path = "git_comparison.rs"]
mod comparison;
use flate2::read::ZlibDecoder;
use std::fs::{self, File};
use std::io::Read;
use std::process::{ChildStdout, Command, Stdio};

const MAX_GIT_OUTPUT_BYTES: u64 = 4 * 1024 * 1024;
const GIT_TIMEOUT: Duration = Duration::from_secs(2);
const GIT_POLL_INTERVAL: Duration = Duration::from_micros(100);

pub(super) fn collect_git_snapshot_detailed(
    cwd: &Path,
    generation: u64,
    cancel: &AtomicBool,
    git: &Path,
) -> (Result<GitSnapshot, String>, bool, WorkerMetrics) {
    let discovery_started = Instant::now();
    let identity = discover_repository(cwd);
    let mut metrics = WorkerMetrics {
        repository_discovery: discovery_started.elapsed(),
        ..WorkerMetrics::default()
    };
    let Some(identity) = identity else {
        return (Ok(empty_snapshot(cwd, generation)), false, metrics);
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
        Err(error) => {
            return (
                Err(format!("could not start Git status: {error}")),
                false,
                metrics,
            );
        }
    };
    metrics.child_processes = 1;
    let mut stdout = child.stdout.take().expect("piped Git stdout");
    let started = Instant::now();
    let mut cancelled = false;
    let collected =
        read_git_while_waiting(&mut child, &mut stdout, cancel, started, &mut cancelled);
    metrics.git_process = Some(started.elapsed());
    if cancelled {
        return (Err("Git request cancelled".into()), true, metrics);
    }
    let (status, output) = match collected {
        Ok(result) => result,
        Err(error) => return (Err(error), false, metrics),
    };
    if !status.success() {
        return (
            Err(format!("Git status exited with {status}")),
            false,
            metrics,
        );
    }
    let parsing_started = Instant::now();
    let result = parse_git_status(cwd, generation, identity, &output);
    metrics.parsing = Some(parsing_started.elapsed());
    (result, false, metrics)
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

fn read_git_while_waiting(
    child: &mut std::process::Child,
    stdout: &mut ChildStdout,
    cancel: &AtomicBool,
    started: Instant,
    cancelled: &mut bool,
) -> Result<(std::process::ExitStatus, Vec<u8>), String> {
    use std::os::fd::AsRawFd;
    let result = (|| {
        let fd = stdout.as_raw_fd();
        let flags = unsafe { libc::fcntl(fd, libc::F_GETFL) };
        if flags < 0 || unsafe { libc::fcntl(fd, libc::F_SETFL, flags | libc::O_NONBLOCK) } < 0 {
            return Err(format!(
                "could not configure Git stdout: {}",
                std::io::Error::last_os_error()
            ));
        }
        let mut output = Vec::new();
        let mut buffer = [0u8; 8192];
        let mut status = None;
        let mut eof = false;
        loop {
            if cancel.load(Ordering::Acquire) || started.elapsed() >= GIT_TIMEOUT {
                *cancelled = cancel.load(Ordering::Acquire);
                return Err("Git output collection interrupted".into());
            }
            let mut progress = false;
            if !eof {
                match stdout.read(&mut buffer) {
                    Ok(0) => eof = true,
                    Ok(count) => {
                        if output.len() + count > MAX_GIT_OUTPUT_BYTES as usize {
                            return Err(format!("Git status exceeds {MAX_GIT_OUTPUT_BYTES} bytes"));
                        }
                        output.extend_from_slice(&buffer[..count]);
                        progress = true;
                    }
                    Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {}
                    Err(error) if error.kind() == std::io::ErrorKind::Interrupted => continue,
                    Err(error) => return Err(format!("could not read Git status: {error}")),
                }
            }
            if status.is_none() {
                status = child
                    .try_wait()
                    .map_err(|error| format!("could not wait for Git status: {error}"))?;
            }
            if eof && let Some(status) = status {
                return Ok((status, output));
            }
            if !progress {
                thread::sleep(GIT_POLL_INTERVAL);
            }
        }
    })();
    if result.is_err() {
        kill_git_child(child);
        let _ = child.wait();
    }
    result
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

pub(super) fn detect_operation(git_dir: &Path) -> Option<GitOperation> {
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
