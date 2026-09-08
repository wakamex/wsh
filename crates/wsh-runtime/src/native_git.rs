//! Temporary comparison bridge. The existing worker, protocol and renderer stay unchanged.
use super::*;
use std::ffi::{CStr, CString, c_char, c_int, c_void};
use std::os::unix::ffi::OsStrExt;

#[repr(C)]
#[derive(Default)]
struct NativeResult {
    root: *mut c_char,
    branch: *mut c_char,
    detached_sha: *mut c_char,
    exact_tag: *mut c_char,
    error: *mut c_char,
    ahead: u64,
    behind: u64,
    discovery_ns: u64,
    process_ns: u64,
    parsing_ns: u64,
    child_processes: u64,
    found: c_int,
    staged: c_int,
    modified: c_int,
    untracked: c_int,
    operation: c_int,
    worktree: c_int,
    cancelled: c_int,
}

unsafe extern "C" {
    fn wsh_git_collect(
        cwd: *const c_char,
        git: *const c_char,
        cancel: extern "C" fn(*mut c_void) -> c_int,
        context: *mut c_void,
        result: *mut NativeResult,
    ) -> c_int;
    #[cfg(test)]
    fn wsh_git_operation(directory: *const c_char) -> c_int;
    fn wsh_git_free(result: *mut NativeResult);
}

impl Drop for NativeResult {
    fn drop(&mut self) {
        unsafe { wsh_git_free(self) }
    }
}
extern "C" fn cancelled(context: *mut c_void) -> c_int {
    // The synchronous call borrows this AtomicBool until the C collector returns.
    i32::from(unsafe { &*context.cast::<AtomicBool>() }.load(Ordering::Acquire))
}
fn string(pointer: *const c_char) -> Option<String> {
    if pointer.is_null() {
        None
    } else {
        Some(
            unsafe { CStr::from_ptr(pointer) }
                .to_string_lossy()
                .into_owned(),
        )
    }
}

pub(super) fn collect_git_snapshot_detailed(
    cwd: &Path,
    generation: u64,
    cancel: &AtomicBool,
    git: &Path,
) -> (Result<GitSnapshot, String>, bool, WorkerMetrics) {
    let (Ok(cwd_string), Ok(git_string)) = (
        CString::new(cwd.as_os_str().as_bytes()),
        CString::new(git.as_os_str().as_bytes()),
    ) else {
        return (
            Err("Git path contains NUL".into()),
            false,
            WorkerMetrics::default(),
        );
    };
    let mut result = NativeResult::default();
    let status = unsafe {
        wsh_git_collect(
            cwd_string.as_ptr(),
            git_string.as_ptr(),
            cancelled,
            std::ptr::from_ref(cancel).cast_mut().cast(),
            &mut result,
        )
    };
    let metrics = WorkerMetrics {
        repository_discovery: Duration::from_nanos(result.discovery_ns),
        git_process: (result.child_processes != 0).then(|| Duration::from_nanos(result.process_ns)),
        parsing: (result.parsing_ns != 0).then(|| Duration::from_nanos(result.parsing_ns)),
        child_processes: result.child_processes,
    };
    if status != 0 {
        return (
            Err(string(result.error).unwrap_or_else(|| "C Git collector failed".into())),
            result.cancelled != 0,
            metrics,
        );
    }
    let snapshot = GitSnapshot {
        schema_version: 1,
        generation,
        cwd_hex: encode_path(cwd),
        found: result.found != 0,
        root_hex: if result.root.is_null() {
            None
        } else {
            Some(encode_hex(
                unsafe { CStr::from_ptr(result.root) }.to_bytes(),
            ))
        },
        branch: string(result.branch),
        detached_sha: string(result.detached_sha),
        exact_tag: string(result.exact_tag),
        staged: result.staged != 0,
        modified: result.modified != 0,
        untracked: result.untracked != 0,
        ahead: result.ahead,
        behind: result.behind,
        operation: match result.operation {
            1 => Some(GitOperation::Rebase),
            2 => Some(GitOperation::Merge),
            3 => Some(GitOperation::CherryPick),
            4 => Some(GitOperation::Revert),
            5 => Some(GitOperation::Bisect),
            _ => None,
        },
        worktree: result.worktree != 0,
    };
    (Ok(snapshot), false, metrics)
}

#[cfg(test)]
pub(super) fn detect_operation(directory: &Path) -> Option<GitOperation> {
    let directory = CString::new(directory.as_os_str().as_bytes()).ok()?;
    match unsafe { wsh_git_operation(directory.as_ptr()) } {
        1 => Some(GitOperation::Rebase),
        2 => Some(GitOperation::Merge),
        3 => Some(GitOperation::CherryPick),
        4 => Some(GitOperation::Revert),
        5 => Some(GitOperation::Bisect),
        _ => None,
    }
}
