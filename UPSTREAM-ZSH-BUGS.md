# Confirmed Zsh bugs for potential upstreaming

This document records local upstream candidates and their submission status. Record the affected source revision, minimal reproducer, expected and observed behavior, proposed fix and verification before considering submission.

## Neutral highlight attributes discard ownership metadata

Affected source: `zsh-users/zsh` commit `cad0d67c76e2be7371cf3526b79ea2581810d35a`. Confirmed using real ZLE on the native development installation before the local fix.

`output_highlight()` serializes an empty attribute mask as `none`, but `match_highlight()` does not consume that token. `set_region_highlight()` therefore stops before following `memo=` or `layer=` fields. A neutral region loses its ownership tag. The syntax-highlighting plugin removes only regions carrying its memo, so these entries survive cleanup, accumulate across redraws and move when the editor inserts text.

Minimal widget reproducer:

```zsh
_probe_highlight_memo() {
  region_highlight=('0 1 none memo=probe')
  typeset -p region_highlight
}
zle -N _probe_highlight_memo
bindkey '^T' _probe_highlight_memo
```

Press Ctrl-T in a real ZLE session. Expected: `region_highlight` retains `memo=probe`. Observed: it becomes `0 1 none`. `fg=green memo=probe` retains the memo. `none,layer=4 memo=probe` loses both layer and memo. The automated reproducer is [native/test-highlight-roundtrip.py](native/test-highlight-roundtrip.py); it records first assignment and subsequent round trips without a fake parameter implementation.

The local patch [cad0d67c-highlight-none.patch](build/zsh-patches/cad0d67c-highlight-none.patch) consumes a delimited `none` token without changing the attribute mask, allowing subsequent attributes and metadata to be parsed. The normal and ASan/UBSan real-ZLE regressions pass all five cases. Host upstream tests, nine installed contracts, all 287 highlighter fixtures, repeated composed redraws and canonical glibc 2.28 qualification pass. The [fix report and retained evidence](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/zsh-highlight-none-2026-09-10/report.md) identify exact builds and test results.

Upstream submission should include a regression in the upstream real-ZLE highlighting tests, explain the serializer/parser mismatch, and check neutral style combinations and malformed token boundaries. No submission has been made.

## OSC 133 identifier and initial OSC 7 reporting

The pinned post-5.9 terminal integration wrote a generated OSC 133 identifier at an incorrect fixed byte offset, corrupting the `aid=z` field name. Its initial OSC 7 report also depended on an optional terminal query, so disabling an unanswered query removed the initial directory report and could leave a foreground application's directory active in the terminal.

The retained [terminal integration report](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-terminal-integration-2026-09-04/report.md) contains reproducers, authoritative terminal-parser checks and validation. The local patch is [cad0d67c-terminal-integration.patch](build/zsh-patches/cad0d67c-terminal-integration.patch). These are confirmed local fixes; this document does not establish their submission or upstream acceptance status.

## Compiled-function alignment padding contains uninitialized bytes

The pinned compiled-function writer rounded program data to whole words and wrote the rounded size from a heap allocation, including up to three uninitialized bytes. Independent builds could produce different compiled-function bytes and include stale heap data.

The retained [reproducibility report](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/zcompile-reproducibility-2026-09-04/report.md) records the reproducer and passing zero-padding/reproducibility checks. The local patch is [cad0d67c-zcompile-padding.patch](build/zsh-patches/cad0d67c-zcompile-padding.patch). This is a confirmed local fix; this document does not establish its submission or upstream acceptance status.

## Monotonic clock compared with file times

Affected source: `zsh-users/zsh` commit `cad0d67c76e2be7371cf3526b79ea2581810d35a`, and upstream `master` at `7708d466df`. The defects were introduced by upstream commit [`6bb792dba8`](https://github.com/zsh-users/zsh/commit/6bb792dba8) ("53257: use monotonic clock where appropriate"). Zsh 5.9 is not affected.

That commit moved several timers to `zmonotime()`, which counts seconds since boot. Three of them are compared with file times, which count seconds since 1970, so every file time looks decades newer than the timer. An audit of every file-time comparison and monotonic clock read in master's `Src/` found these three; the remaining monotonic uses measure intervals, and the remaining file-time comparisons use `time()` or other file times.

### Stale history locks are never broken

`lockhistfile()` writes `HISTFILE.LOCK` while saving history. When it finds an existing lock, `checklocktime()` deletes the lock once it is more than 10 seconds old, which recovers from a shell killed while saving. Its `now` comes from `zmonotime()` and its `then` from the lock's `st_mtime`, so every lock appears more than 10 seconds in the future, `checklocktime()` fails with `EEXIST`, and the stale lock is never removed. Every later history save fails with `locking failed for HISTFILE: file exists` until the user deletes the lock by hand. Killing all shells at once, for example by restarting a terminal multiplexer service, makes this likely.

Minimal reproducer with `HISTFILE=~/.zsh_history` and `INC_APPEND_HISTORY` in a real interactive shell:

```sh
ln -s /pid-1/host-stale ~/.zsh_history.LOCK
touch -h -d '5 minutes ago' ~/.zsh_history.LOCK
zsh -i    # then run any command and exit
```

Incremental saves try the lock once without waiting, so the save at exit is the one that checks the lock's age. Expected: the exit save removes the lock and saves the command, as in Zsh 5.9. Observed: the lock remains, the command is not saved, and every shell reports `locking failed`.

### Lock backoff ignores the lock's expiry

While a lock is younger than 10 seconds, `checklocktime()` sleeps through `zsleep_random(max_us, then + 10)`, which shortens a doubling random backoff so that it does not sleep past the deadline. `zsleep_random()` reads `zmonotime()`, and its other caller passes a monotonic deadline, but `then + 10` is a file time. The cap therefore never applies, and the exit save can sleep several seconds past the lock's expiry before breaking it.

### Unread mail is announced at every check

`lastmailcheck` is set from `zmonotime()` and compared with the mailbox's `st_mtime` to detect new mail, and with `st_atime` for `MAIL_WARNING`. Both comparisons are always true, so a nonempty unread mailbox prints `You have new mail.` at every mail check, every 60 seconds by default, instead of once after delivery. With `MAIL_WARNING`, an old read mailbox prints `The mail in FILE has been read.` at every check.

Minimal reproducer:

```sh
print 'From sender\n\nbody' > ~/box
touch -m -d '1 hour ago' ~/box; touch -a -d '61 minutes ago' ~/box
MAIL=~/box MAILCHECK=1 zsh -f -i    # press Enter a few times, two seconds apart
```

Expected: no notice, as in Zsh 5.9, because the mail arrived before the shell started. Observed: `You have new mail.` after every check.

### Fix and verification

The local patch [cad0d67c-file-time-clock.patch](build/zsh-patches/cad0d67c-file-time-clock.patch) compares the lock age and mail times with `time(NULL)`, as Zsh 5.9 did, and converts the lock's expiry to a monotonic deadline before calling `zsleep_random()`. The mail check interval also uses wall-clock time again, so a clock change can make one check early or late.

Real PTY login-session regressions cover each defect: the stale and fresh lock cases in [tests/history-persistence.py](tests/history-persistence.py) check symlink and regular-file locks and the exit wait, and [tests/mail-check.py](tests/mail-check.py) checks old unread mail, a new delivery announced exactly once, and old read mail with `MAIL_WARNING`. Upstream submission should explain the shared cause and add history and mail tests with aged files. No submission has been made.
