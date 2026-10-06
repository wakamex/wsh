# Ctrl-C at a busy prompt

Pressing Ctrl-C at the Wsh prompt sometimes failed to start a fresh prompt when the machine was busy. The test below presses Ctrl-C while an autosuggestion request is pending, on a host with every CPU running a busy loop, and checks that a fresh prompt returns and the shell still runs commands. With all of Wsh 0.4.5's interrupt fixes, it passed 800 of 800 runs. Builds without the loop break-count fix failed 8 of 1,200.

## Test

Each run starts the installed shell in a pseudo-terminal through the installed autosuggestion suite, binds a widget that starts a 30-second suggestion request, sends Ctrl-C, waits up to 60 seconds for a fresh prompt and then requires the shell to answer a typed command. A transient user unit runs one lowest-weight busy loop per CPU for the whole batch. [Evidence](evidence.tar.gz) retains the harness (`lifecycle-timed.py`, `installed-timed.py`), the exact commands and every batch's output, covered by `SHA256SUMS`.

## Results

| Build, by native installation identity | Interrupt fixes included | Passed runs |
| --- | --- | --- |
| `89754bc0` | Native errflag restores, always-block patch, editor-wait patch | 396 of 400 |
| `c1646934` | As above, and autosuggestion cancel clearing errflag | 398 of 400 |
| `1b79627e` | As above, and cancel queueing signals | 398 of 400 |
| `8c95a118` | Native errflag restores, always-block, editor-wait and loop break-count patches | 800 of 800 |

Every failure had the same signature: a fresh prompt appeared, then the shell used a full CPU and ignored input. The raw output of the `89754bc0` batch was not retained; its four failures were recorded as timeouts at the same pending-cancel step. The two cancel variants did not change the failure rate and were dropped, so `8c95a118` carries the autosuggestion code of 0.4.4.

## Cause

At the hang, Zsh's `breaks` counter was 1 with no loop running. A positive `breaks` makes Zsh skip every command list, so precmd's cancellation never ran, and the autosuggestion `zle -F` handler was called in a busy loop on a pipe whose writer had exited, without its body ever running. A debug Zsh build that recorded the counters captured the source: a SIGINT inside a `for` loop with two loops active set `breaks` to 2, the `for` loop ended with the interrupt flag set without consuming its count, and the excess reached top level ([decoded events](evidence.tar.gz), `ring-buffer.txt`). The [bug record](../../UPSTREAM-ZSH-BUGS.md#an-interrupt-can-leave-a-break-count-after-every-loop-has-ended) describes the defect and the patch.

A widget running a million short `for` loops, interrupted 300 times on an idle machine (`break-leak.py`), never left a count behind on either Zsh 5.9 or the pinned build, so the defect has no deterministic shell reproducer; the window is a few instructions wide and host load widens it.

## Scope

The `8c95a118` installation was built from the same source as the published 0.4.5 native installation `7cf9725d` with a different Zsh output directory. The complete installed suite and both upstream Zsh suites passed on `7cf9725d`.
