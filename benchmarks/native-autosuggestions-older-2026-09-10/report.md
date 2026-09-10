# Older upstream autosuggestion ownership

The user's unchanged v0.7.0 autosuggestions now uses Wsh's existing native controller. Suggestion display and acceptance pass with the actual `.zshrc` in both Wsh and regular Zsh, with startup files unchanged. Isolated startup improves by about 5-6 ms at the median across 50 alternating pairs per prompt mode.

| Prompt mode with upstream v0.7.0 sourced in startup | External plugin median readiness | Native takeover median readiness | Paired p95 added readiness | Gate |
|---|---:|---:|---:|---|
| Existing prompt | 24.592 ms | 18.906 ms | -4.805 ms | <= 3 ms, pass |
| Wsh minimal prompt | 24.827 ms | 19.637 ms | -4.892 ms | <= 3 ms, pass |

## Baseline and fixed gate

At baseline `7bbee20`, the user's unchanged upstream v0.7.0 copy is classified as external-unknown despite reaching Wsh initialization with zero bound widgets and no asynchronous request. Relative to pinned v0.7.1, it differs in two default clear-widget entries, clearing POSTDISPLAY, explicitly invoking builtin exec and clearing asynchronous fd bookkeeping. The smallest intervention adds its exact source as a recognition reference and uses the already qualified native controller for inactive copies. Existing configured values are preserved.

Before testing, require real editor suggestion/acceptance parity and preserved colors/widget lists, custom strategies, modified sources/functions, active copies and explicit disable behavior. Verify real OMZ and the user's actual configuration, and run the installed controller's lifecycle/bounds cases. Measure 50 alternating startup pairs per prompt mode with a paired p95 overhead gate of <= 3 ms. Two failed interventions at one gate require a new hypothesis.

## Version comparison and ownership

The user's `/code/zsh-autosuggestions/zsh-autosuggestions.zsh` exactly matches upstream commit `a411ef3e0992d4839f0732ebeb9823024afaaaa8`, verified against local Git objects. Relative to that v0.7.0 source, pinned v0.7.1 adds `history-beginning-search-forward-end` and `history-beginning-search-backward-end` to the default clear-widget list, changes five `unset POSTDISPLAY` calls to empty assignments, explicitly invokes `builtin exec` in three fd operations and clears asynchronous fd bookkeeping after response cleanup. The complete difference is retained in `upstream.diff`.

No C controller changes are required. Wsh compares the loaded source against either exact reference, checks implementation-function provenance, then takes ownership before widgets or asynchronous requests become active. Generated original-widget captures and bound wrappers have caller provenance and are excluded from the function check; their active binding state still prevents takeover. Added named strategies remain supported. Modified files, runtime implementation overrides, already-active copies and explicit disable behavior retain their existing owner.

Existing values remain authoritative, including colors, strategy order, widget lists and asynchronous configuration. The older source initializes its own default widget lists before Wsh runs, so those lists remain intact. Wsh does not guess whether a configured value was a user preference or an old upstream default.

## Correctness and reproduction

All nine host installation contracts pass. The autosuggestion contract covers 11 ownership/configuration cases on the host and glibc 2.28. Real OMZ loading passes 11 cases spanning both recognized versions, pending and active ownership, modified copies, disable behavior, automatic rebinding, custom strategies, completion coexistence and doctor advice. The installed controller matches upstream across ten editor modes and passes pending-request cancellation, prompt return, fd cleanup, child reaping and oversized-response rejection. The fresh host Zsh build passes 75 upstream test scripts with zero failures and two skips.

The personal configuration test sources the actual `.zshenv` and `.zshrc` through a private ZDOTDIR shim and isolates history output. It verifies external ownership in regular Zsh and native ownership in Wsh, then seeds history, displays and accepts the same suggestion in both editors. Configuration hashes remain unchanged. Its sanitized result is retained; personal traces and the harness remain under `/var/tmp/wsh-autosuggest-older/user`.

Run `zsh tests/autosuggestions.zsh INSTALLATION`, `python3 native/test-autosuggestions-omz.py INSTALLATION OMZ_CHECKOUT OUTPUT`, and `python3 native/test-installed-autosuggestions.py INSTALLATION OUTPUT MODE` for each of `correctness`, `lifecycle` and `bounds`. Run `python3 native/check-installation.py INSTALLATION OUTPUT` for the full host contracts with the reference/test Zsh and optional OMZ environment described in DEVELOPMENT.md.

The glibc 2.28 fixture reuses the previously qualified executable with the current adapter and older reference overlaid, followed by an inventory refresh and verification. This is a scoped component run; the RPM and sanitizers were not rebuilt for this recognition-only change. The C controller is unchanged from its prior qualification. All installations are unsigned development artifacts.

## Timing and retained inputs

Run `python3 native/measure-older-autosuggestions.py BASELINE_INSTALLATION CANDIDATE_INSTALLATION OUTPUT`. Both variants source the same v0.7.0 bytes and use CPU 0, tracing off, a private non-Git working directory and native OSC 133 B readiness. Each prompt mode uses 50 alternating pairs; paired p95 is sorted index 47 and the reported median uses index 24. Timing starts before the PTY fork. Correctness runs precede timing.

These startup figures isolate the plugin takeover and do not represent the full personal configuration's startup time. The benchmark does not remeasure the already-qualified C editing speedup. `identity.json` records source, compiler, target, build command and binary identities; `evidence.tar.gz` retains manifests, source lock, generated adapter, raw samples, summaries, commands and test logs. `python3 benchmarks/verify-older-autosuggestions.py` verifies identities, correctness results and the recomputed fixed timing gate through the shared retained-evidence entrypoint.
