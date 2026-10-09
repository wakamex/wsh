# wsh terminal integration

The bundled Zsh now owns standard OSC 7 working-directory reporting and OSC 133 prompt and command zones. Wakterm can omit its duplicate reporters when it launches Wsh while retaining its separate OSC 1337 metadata. Pane history uses the terminal-provided logical token and merges into shared history on exit. Terminal diagnosis and allowlisted metadata remain separate experiments.

The accepted boundary is small: Zsh emits established terminal protocols from the native command and ZLE paths, Wsh carries two measured corrections and brackets its one synthetic first job, and the terminal consumes those sequences without understanding shell source or job-control mechanics.

Wsh sets the default `-query` policy before loading user `.zshenv`, because completion initialization there can already load ZLE. Set `WSH_ENABLE_ZLE_TERMINAL_QUERY=1` in the launch environment to opt in before startup. An explicit `.term.extensions` assignment in user startup remains authoritative and must precede the first ZLE load to control its queries.

## Existing protocols cover the basic contract

| Capability | Existing mechanism | Owner | Terminal feature enabled |
|---|---|---|---|
| Current working directory | OSC 7 with a `file://host/path` URI | Native Zsh emits before each editable prompt | Open a new pane or tab in the same directory and display remote context correctly |
| Prompt and output zones | OSC 133 `A`, `B`, `C`, and `D` markers | Native Zsh marks ordinary prompts and commands; Wsh brackets only an exact first foreground application | Jump between prompts, select command output, distinguish idle shells, and improve close confirmation |
| Pane metadata | OSC 1337 user variables where supported | Terminal integration publishes a small allowlisted set after state changes | Terminal status, tab titles, rules, and multiplexing based on project or command state |

[WezTerm documents OSC 7, OSC 133, and OSC 1337](https://github.com/wezterm/wezterm/blob/main/docs/shell-integration.md), and [Windows Terminal documents the OSC 133 command lifecycle](https://learn.microsoft.com/en-us/windows/terminal/tutorials/shell-integration). [Ghostty uses shell integration](https://ghostty.org/docs/features/shell-integration) for working-directory inheritance, prompt navigation, output selection, close safety, cursor behavior, and prompt redraw. Wsh uses these established sequences once rather than defining a private protocol.

## Terminal diagnosis separates observed failures from inferred quirks

`wsh doctor terminal` can diagnose many compatibility failures without treating a terminal name as authoritative. Its strongest results come from behavior and captured bytes: duplicate OSC markers, incorrect lifecycle order, status corruption, prompt-time child processes, blocking queries, unexpected replies, leaked protocol text, conflicting integration owners, and components that remain enabled after the terminal or multiplexer says they are unsupported.

Terminal identity is layered evidence rather than one fact:

| Evidence | Useful conclusion | Limit |
|---|---|---|
| Explicit terminal identity and capability values supplied when the pane is created | The terminal states what it is and which integration it intends to support | Environment values can be inherited, forwarded, stale, or set by another program |
| `TERM`, terminal-specific variables, local process ancestry, SSH state, container state, and multiplexer variables | A likely topology and a list of components that may mediate protocol traffic | `tmux`, Screen, SSH, nesting, wrappers, and restored sessions can hide or replace the outer terminal |
| Safe terminal queries with bounded replies | A responding endpoint's reported identity or capability | A multiplexer may answer, forward, rewrite, or swallow the query, and an unresponsive terminal must never delay the prompt |
| An isolated diagnostic Zsh captured through a PTY | Exact shell output, hooks, process count, marker count, ordering, status, and disable behavior | It observes bytes before the terminal renders them and therefore cannot see every visual or terminal-policy failure |
| A versioned compatibility rule tied to a reproduced issue | A likely affected terminal/version/topology and a tested component-level workaround | A match is a recommendation, not proof that the current session exhibits the failure |

The default doctor is passive. It records the exact `wsh` and Zsh build, enabled terminal components, integration owners, relevant environment and topology evidence, and a redacted lifecycle trace. An explicit probe mode may run only bounded reply-producing queries and an isolated diagnostic shell. Every query has a short deadline and byte limit, does not run on the ordinary prompt path, and restores any terminal mode it changes.

OSC 133 itself has no success acknowledgement. A failure such as [Konsole reacting badly to otherwise valid prompt markers](https://fishshell.com/docs/current/relnotes.html) may therefore be invisible to automatic probing. The doctor can still recognize a likely affected version or topology from a reproduced compatibility rule and recommend disabling only OSC 133 while leaving OSC 7 and unrelated integration enabled. It must label that result as inferred unless the session supplies observable confirming behavior.

Compatibility rules stay small and evidence-backed. Each rule records the terminal and affected versions, relevant nesting or multiplexer conditions, the reproducer or upstream issue, the failing component, the exact reversible setting, and the version or test that retires the workaround. Rules ship with the tested `wsh` build rather than updating from an unauthenticated network source. A recommendation identifies one independently controllable component such as OSC 7, OSC 133, OSC 1337 metadata, terminal queries, notifications, or enhanced keyboard mode. The doctor never changes configuration automatically.

Useful output is direct:

```text
observed: OSC 133 command markers were emitted twice
owners: native Zsh and Wakterm shell injection
recommendation: let Wakterm skip its OSC 7 and OSC 133 reporters when launching wsh

inferred: this Konsole version matches a reproduced OSC 133 compatibility rule
recommendation: disable native OSC 133 prompt markers and keep OSC 7 enabled
verification: rerun the lifecycle capture after changing the setting
```

The diagnostic passes only if disabling the named component removes the reproduced failure while unrelated components continue to pass. A generic terminal compatibility database, automatic configuration repair, visual screenshot interpretation, and broad terminal fingerprinting remain deferred until concrete cases require them.

## Native Zsh replaces Wakterm's duplicate standard reporters

Wakterm's shell integration emits OSC 7, OSC 133, and OSC 1337 and can run `wakterm set-working-directory` from its prompt hook. The pinned post-5.9 Zsh already emitted OSC 7 and OSC 133 natively, so enabling both paths produced duplicate prompt, command, output, and directory markers. The retained workload also observed nine `wakterm set-working-directory` executions.

Native Zsh initially failed two correctness gates. A fixed byte offset overwrote the `aid=z` field in every OSC 133 prompt-start marker, so Wakterm's authoritative parser accepted 0 of 10 prompt starts. Wsh's measured decision to disable the optional terminal query also suppressed the native initial OSC 7 report, and a foreground child that emitted a remote directory could leave that stale value active after returning.

The smallest accepted source patch writes the generated prompt identifier into its named placeholder and reports the current directory from the native prompt path. The patched workload produced 10 valid prompt starts, 10 prompt ends, 7 command starts, 6 command ends, 10 local-directory reports, one verified reset after child output, 9 user `precmd` calls, and 7 user `preexec` calls. Empty input produced another prompt without a false native command region. It passed Wakterm's real parser and all 75 upstream Zsh test scripts, with 0 failures and 2 existing skips.

Wsh sets `WSH_NATIVE_TERMINAL_INTEGRATION=1` before startup. Wakterm uses it to skip only its OSC 7 and OSC 133 paths while retaining OSC 1337 metadata. The accepted coexistence path matched native-only correctness counts and executed no prompt-time Wakterm process. In 40 retained interleaved runs after 5 warmups, 100 no-op prompt cycles took 60.500 ms at p90 under coexistence and 60.552 ms under native-only, passing the fixed maximum regression of 0.5 ms. Leaving both reporters active took 499.381 ms at p90. The [retained report](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-terminal-integration-2026-09-04/report.md) contains raw transcripts, timings, process traces, exact identities, and reproduction commands.

## Pane history recalls the pane's own commands first

Wakterm supplies `WAKTERM_PANE_TOKEN`, a lowercase UUID for the logical pane. It remains stable across shell replacement and mux restore; new panes receive new tokens. Wsh uses this token by default in the outermost interactive shell. Without a valid token, ordinary shared-file history remains active. Numeric pane IDs are not used as durable identity.

A new shell first loads the configured shared `HISTFILE`, then appends that pane's retained history to its in-memory list. Up and history search therefore encounter the pane's recent commands first, with shared history available behind them. Each command is written to the shared history as it runs, so a new shell in any pane can recall commands from panes that are still open. Already-open panes do not import other panes' new commands, which keeps Up in each pane on that pane's work. Live sharing, Zsh's `share_history` option, interleaves other shells' commands with the pane's own; Wsh turns it off when Oh My Zsh enabled it and keeps it when a user's own startup files set it.

Storage is `${XDG_STATE_HOME:-$HOME/.local/state}/wsh/history/panes/<uuid>.zsh`, with a `.journal` and `.owner` lock beside it. Only canonical lowercase UUID filenames are accepted. These are Wsh-owned files; the generic Wakterm Bash/Zsh adapter uses its own directory. `HISTSIZE` bounds active memory and `SAVEHIST` bounds saved entries per file. Zsh's parser, history contexts, file locks and retention rules handle file merging. No database, daemon or keypress-time disk lookup is involved.

Each command is appended to the journal before it is written to the shared history. Normal exit merges the journal into the pane file; after SIGKILL or `exec`, the next shell with the same token recovers it. A failed merge retains the journal for retry. If the shared history cannot be written, commands still reach the pane file, and Zsh retries the shared write at later saves in the same session. A `.pending` journal left by Wsh 0.4.6 or earlier, which published commands only on exit, merges into both the shared history and the pane file. Unused pane files are not automatically garbage-collected.

Wsh keeps the configured `HISTFILE` unchanged and journals only automatic saves from the owning history context. Nested interactive shells retain the configured shared path, including exported custom paths. A process lock prevents two live owners from using the same token. `WAKTERM_PANE_HISTORY_OWNER` contains the owner's PID and is exported for the generic adapter; `WSH_NATIVE_PANE_HISTORY=1` is local to the Wsh process and makes Wakterm's adapter step aside. `exec` preserves the PID and can recover ownership. The token is a storage identifier, never authority over other processes.

## History opt-outs and private contexts

Set `WAKTERM_SHELL_SKIP_PANE_HISTORY=1` to keep ordinary shared history. An empty or unset `HISTFILE`, `SAVEHIST=0`, noninteractive execution, `-f`, or an already-pushed history context prevents pane activation. Unusable private storage also leaves ordinary history available. An invalid or relative `XDG_STATE_HOME` uses the standard home-directory fallback. Existing shared-history configuration is preserved when pane mode is inactive.

Pane mode disables live `SHARE_HISTORY`. It selects incremental saving, preserving `INC_APPEND_HISTORY_TIME` when configured. This policy is deliberately stronger than an existing exit-only or live-sharing preference; use the pane opt-out to retain those preferences. Changes to `HISTFILE`, disabled saving, a pushed history context, or re-enabled live sharing stop native journal routing for that context.

A memory-only `fc -p` context does not write to the pane journal. `fc -P` returns to the original history context. This supports Zsh's existing private-history mechanism; it does not introduce a new privacy command or disable third-party history collectors. Terminal scrollback, command output and application-managed files remain outside shell-history ownership.

## Pane restoration qualification

`tests/pane-history.py` drives real PTY shells through separate tokens, merge-on-exit, shared-then-pane recall, SIGKILL recovery, `exec`, nested shells, duplicate owners, retention, failed merges and opt-outs. Set `WSH_TEST_WAKTERM` to the actual `wakterm.sh` to test that only the native owner runs. The shared installed suite includes the self-contained cases.

Wakterm owns persistence and restoration of the logical token. Its token and shell-adapter commits still require terminal-side deployment and an end-to-end mux restart check with the matching Wsh build. The shell test recreates the same token; it does not itself restart Wakterm. Shell history remains separate from terminal scrollback restoration.

## Native command zones have one owner

The bundled Zsh emits:

```text
OSC 133 ; A ST    prompt begins
OSC 133 ; B ST    prompt ends and editable input begins
OSC 133 ; C ST    command output begins
OSC 133 ; D ST    command finishes
```

The current upstream implementation does not attach exit status to `D`, and no current Wakterm behavior requires it. Adding structured results remains evidence-gated. The retained fixture covers successful and failed commands, directory changes, multiline input, output without a trailing newline, Ctrl-C while editing, user hooks, and a child-emitted directory report. Terminal-specific integrations must not emit a second copy of the same markers.

OSC 133 enables useful terminal behavior without revealing the command text. A terminal can identify the most recent prompt and output region, implement jump and select-output actions, and distinguish an idle prompt from a running command. Close confirmation still remains a terminal policy because the terminal also knows about foreground processes and pane visibility.

## Native directory reports restore shell context

Before each editable prompt, native Zsh emits OSC 7 using the current host and an encoded absolute path. Reporting at that boundary restores shell context after any foreground child emitted its own cwd. Over SSH or inside a container, the host component describes the context that owns the path rather than the local terminal host. Terminals can then avoid treating a remote path as a local directory when creating a new pane.

Project root is separate from current directory. When metadata is supported, `wsh` can publish an encoded project identifier or display-safe project name, but the terminal should use OSC 7 for directory inheritance.

## Pane metadata is small and allowlisted

Terminals that support OSC 1337 user variables can receive a stable set of fields such as:

```text
wsh.project_name
wsh.git_branch
wsh.command_state
wsh.remote_host
```

Values are bounded, change only when their source snapshot changes, and are cleared explicitly when they stop applying. Wakterm's current integration can publish the full command line through `WAKTERM_PROG`; the comparison verifies that the allowlist supplies the fields used by terminal UI without that value. Full paths, full command lines, arbitrary environment variables, repository remotes, tokens, and command output are excluded by default.

The baseline opens an ordinary shell or detected agent in a Git repository, verifies that `git branch --show-current` reports a branch while Wakterm's navigator shows no branch, runs a harmless distinctive command, and confirms through pane user variables that `WAKTERM_PROG` exposes its complete text. The lifecycle process trace also counts metadata-related children.

The cheapest counterfactual removes `WAKTERM_PROG` and other unused variables. If branch display remains desirable, Wakterm first samples Git state only while the navigator is open through its existing resource snapshot or cache path. `wsh.git_branch` is accepted only when the existing `wsh` Git provider already has the value and publishing it avoids a measured Wakterm Git query. The pass condition is prompt branch display with no Wakterm Git subprocess and no full command text in user variables.

OSC user variables are presentation hints, not an authenticated control channel. A program running in the pane can emit terminal sequences too, so terminals must not grant filesystem, process, or remote-control authority solely from these values.

## Progress and notifications require concrete terminal cases

The shell knows whether a command is running, how long it has run, how it exited, and whether jobs remain. It generally does not know an arbitrary application's percentage complete, which remains application-owned. Indeterminate state or [OSC 9;4 progress](https://learn.microsoft.com/en-us/windows/terminal/tutorials/progress-bar-sequences) becomes `wsh` work only after a terminal workflow demonstrates that application reporting or existing shell integration is insufficient.

For long-command notifications, the candidate division remains that `wsh` knows duration and exit status while the terminal knows focus and visibility. This matches protocols such as [Kitty's desktop notifications](https://sw.kovidgoyal.net/kitty/desktop-notifications/). No notification integration is accepted until a reproducible missed or duplicate notification demonstrates an improvement over terminal configuration alone.

## Shell cloning remains deferred

[Kitty's shell integration](https://github.com/kovidgoyal/kitty/blob/master/docs/shell-integration.rst) demonstrates that shell cloning can be useful, but Wakterm has not supplied a concrete missing workflow that justifies a state-transfer contract. Current-directory inheritance and pane-history ancestry are covered by narrower mechanisms. Jobs, arbitrary environment, functions, aliases, credentials, sockets, command output, and process state remain excluded. A broader manifest requires a reproducer and explicit benefit before design resumes.

## Remote and container adapters require a path failure reproducer

Terminal injection can disappear after switching shells, entering a container, or connecting to a host without matching dotfiles. A `wsh` adapter requires a reproduced lifecycle or local-versus-remote path failure and an owner for mapping that context. It should not silently copy executable integration code or user configuration to a remote host.

The remote side emits its own OSC 7 and OSC 133 events. Local terminals interpret them, while `wsh` marks metadata as remote and avoids offering local clone or path operations for a remote filesystem unless the terminal explicitly supports that mapping.

## Capability advertisement remains an additive hint

A terminal can optionally set an allowlisted capability declaration when it creates the pane:

```sh
WSH_TERMINAL_CAPABILITIES=osc7,osc133,osc1337,osc9-4,notify,kitty-keyboard
```

This is a hint, not a security claim or handshake. It becomes necessary only when a terminal-name or version heuristic is shown to select incorrect behavior. `wsh` can combine it with standard environment and terminfo data, and query only protocols with safe, bounded replies. Unknown capabilities are ignored, and integrations tolerate a missing declaration.

Enhanced keyboard integration remains deferred. Wakterm already implements the [Kitty keyboard protocol](https://sw.kovidgoyal.net/kitty/keyboard-protocol/), and no current Wakterm-specific ZLE ambiguity demonstrates that `wsh` must request or manage its progressive modes.

## Command recall and rendered scrollback have different owners

`wsh` restores bounded command recall used by Up and Down. Wakterm owns bounded rendered primary-screen scrollback, cell attributes, hyperlinks, semantic zones, viewport position, compression, and restoration boundaries. Applications own their durable provider or conversation state. None of these layers claims to restore live processes, the shell job table, PTY state, or alternate-screen runtime state.

Wakterm currently restores layout without terminal content. Its separate experiment can extend `scripts/bench_restored_mux.py` with deterministic primary-screen text, attributes, a hyperlink, and OSC 133 zones, then compare retained content across restart for 1, 5, and 20 panes. Line and semantic-zone hashes, compressed bytes, save and restore latency, PSS, and write syscalls measure a bounded compressed snapshot stored separately from the frequently rewritten layout JSON. This remains a Wakterm terminal and mux feature and does not justify command-output capture in `wsh`. The logical pane token may associate the two restoration products, but it grants neither layer authority over the other.

## Terminal-rendered completion remains a later experiment

A terminal could eventually render completion candidates received over authenticated local IPC, especially when it already owns a command palette or rich pane UI. It should not receive candidates through unbounded escape-sequence payloads, and terminal rendering is not part of the Wakterm endpoint experiment. The Zsh adapter in [`COMPLETION.md`](COMPLETION.md) first needs to establish replacement ranges, grouping, quoting, descriptions, cancellation, and fallback semantics.

The same local IPC could later support clone tokens, pane-close hints, metadata subscriptions, or output-region identifiers. Those uses should share one authenticated connection rather than introduce an escape sequence for each feature, but no IPC service is needed for the basic pane token and OSC integration.

## Experiments are incremental

| Experiment | Terminal work | Required result |
|---|---|---|
| Native lifecycle | Accepted: Wakterm skips its OSC 7 and OSC 133 reporters for Wsh and consumes the native sequences | Retain valid parser output, correct directory restoration, zero duplicate markers, zero prompt-time Wakterm processes, and the prompt-cycle latency gate |
| Foreground jobs | Accepted owner-local fix: keep Wakterm's cached native-frontend identity while its fixture passes | Managed identity clears after exit or replacement, survives stop and continue, and cannot transfer to a new frontend |
| Pane restore | Persist and export `WAKTERM_PANE_TOKEN` | A restored pane recalls its own recent commands first, retains shared recall and recovers pending commands; qualify the deployed mux restart path |
| Private history | Push a fresh memory-only history context and disable durable adapters | Sentinel commands remain available only during the private context and never enter `wsh` files, indexes, metadata, or default traces |
| Metadata | Consume the versioned allowlist and explicit clears | Project-aware UI works without a full command line or arbitrary variables |
| Terminal doctor | Capture one isolated lifecycle and compare only reproduced compatibility rules | Observed failures name their owner, inferred quirks state their confidence, and each recommendation disables one component reversibly |

Notifications, progress, remote adapters, enhanced keyboard management, transient prompt coordination, shell cloning, terminal-rendered completion, automatic compatibility repair, and broad terminal fingerprinting remain outside this sequence until their own reproducers pass the feature admission rules in [`FEATURES.md`](FEATURES.md).

## Validation covers bytes, lifecycle, nesting, and secrecy

The accepted native fixture covers fresh prompts, empty input, successful and failed commands, editing interruption, multiline input, output without a trailing newline, directory changes, child-emitted OSC 7, hook preservation, exact first-job startup, component disablement, and Wakterm's authoritative parser. Syntax errors, `exec`, nested shells, multiplexers, SSH, and containers remain additions when a concrete consumer case requires them.

Protocol tests inspect exact emitted bytes with a headless parser. Interactive tests verify that one event produces one marker, prompt latency does not depend on terminal acknowledgement, unsupported terminals display no protocol debris, and disabling integration restores ordinary Zsh behavior. Privacy tests place secrets in arguments, environment values, paths, and Git configuration and verify that default metadata, notifications, history filenames, and logs do not expose them.
