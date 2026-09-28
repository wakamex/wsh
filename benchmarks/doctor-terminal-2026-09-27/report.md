# Doctor timeout with a controlling terminal

`wsh --doctor` timed out from a real terminal even with an empty configuration. Detaching its diagnostic child into a new session fixes the failure. The new regression failed against packaged `0.4.1`, then passed against the fixed development build on the host and glibc 2.28 floor. Doctor also completed with the local user's configuration from a real terminal.

## Cause and change

Doctor created a separate process group for its interactive diagnostic child while retaining the caller's controlling terminal. The terminal still belonged to the parent's foreground group. During interactive startup, Zsh stopped the background child on terminal access; the parent waited until its ten-second deadline. Redirecting standard input/output to `/dev/null` did not remove the controlling terminal. The observed child process state was stopped, while the parent remained in the terminal's foreground group.

The child now calls `setsid()` to establish a session and process group without a controlling terminal. The parent no longer calls `setpgid` on it, because making the child a group leader first would prevent `setsid()` from succeeding. Existing direct-child and process-group cleanup remains in place. This is a Wsh diagnostic-process setup defect, rather than a confirmed upstream Zsh defect.

## Fixed gate and results

The counterfactual was to run the existing executable through `setsid --wait wsh --doctor`. It returned a complete ownership report from a real terminal with the local configuration. The regression requires clean and background-child cases to succeed within five seconds, interruption to return 130 within five seconds, and a genuinely blocked startup to return the existing timeout error within thirteen seconds. It verifies recorded children are no longer running.

| Check | Result |
| --- | --- |
| Packaged 0.4.1 with empty configuration | Pipe invocation passed; controlling-terminal invocation failed after ten seconds with the reported diagnostic errors |
| Existing executable through `setsid --wait` | Returned a complete report from a real PTY with the local user's configuration |
| Fixed build on host and glibc 2.28 floor | All four terminal, background-cleanup, interruption and timeout cases passed |
| Fixed build with local configuration | Returned a complete report from a real controlling terminal |
| Upstream and installed suites | Reference and native upstream suites each passed 75 scripts with zero failures and two skips. Full installed correctness and RPM agreement checks passed |
| Integration coverage | The terminal regression now runs in the shared installed suite used by canonical and source-RPM builds |

## Reproduction and evidence

Run `python3 tests/doctor-terminal.py /path/to/wsh OUTPUT`. The accepted build was an unsigned development artifact from the glibc 2.28 SDK. [Identity](identity.json) records source and binary hashes. [Evidence](evidence.tar.gz) retains the baseline failure transcript, workaround output, fixed source and regression, host/floor results, installed manifest, exact build command and full build/test logs. `SHA256SUMS` covers retained inputs.

Published in [COPR 0.4.2](../copr-0.4.2/report.md). The `setsid --wait wsh --doctor` command remains a workaround for installed `0.4.1`.
