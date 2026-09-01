# Wakterm dynamic completion experiment

Wakterm currently ships 9,246 lines of generated completion across Bash, Fish, and Zsh even though its live Clap model remains authoritative. This establishes duplicated generated structure and installed size, but it does not yet establish that a resident endpoint is faster or equally correct. The first experiment compares the current assets with direct dynamic completion and a Wakterm-owned mux endpoint.

Zsh continues to own candidate matching, grouping, presentation, and selection. Wakterm owns its command model. A generic broker is not part of this experiment and becomes a candidate only if a second application demonstrates the same lifecycle need. Caching remains optional and provider-specific because broad caching would produce stale paths, configuration, repository state, credentials, or remote results.

## A Wakterm endpoint complements native Zsh completion

Zsh already has a rich completion system with shell-local context, matching, grouping, descriptions, and selection behavior. The endpoint should not replace it. A ZLE adapter sends structured context only for Wakterm commands and converts the response into ordinary Zsh candidates. Conventional completion functions remain the fallback.

```text
command line and cursor
          |
          v
    small ZLE adapter
          |
          v
 Wakterm mux completion endpoint
              |
              v
       live Clap command model
          |
          v
 structured candidates
          |
          v
 Zsh grouping and selection
```

This boundary could:

- Amortize executable startup and command-model construction across Tab presses.
- Let an application expose its authoritative command model without generating a large shell program.
- Give the Wakterm provider one place for deadlines, cancellation, supervision, and observability.
- Reuse an explicitly keyed result when Wakterm can define safe freshness.
- Keep shell adapters small while preserving shell-native presentation.

The experiment must also measure:

- One IPC round trip is added to a latency-sensitive interaction.
- The mux can become a completion failure domain unless the adapter fails quickly to static or native completion.
- Environment filtering and provider registration become security boundaries.
- A generic candidate schema may lose Zsh-specific behavior if it is too narrow.
- Incorrect cache identity can return plausible but stale candidates.

## Existing shells and external completers validate the split

The shell-to-provider split has useful prior art. [Fish](https://fishshell.com/docs/current/interactive.html#tab-completion) already provides a strong shell-native completion engine, descriptions, filtering, and a pager while loading command-specific scripts on demand. [Nushell external completers](https://www.nushell.sh/book/custom_completions.html#external-completions) receive command spans and return structured values and descriptions, with native file completion as a fallback. [Carapace bridges](https://carapace-sh.github.io/carapace-bin/spec/bridge.html) adapt several CLI frameworks and shell completion engines into one multi-shell completer, while documenting startup benefits and edge cases in cross-shell translation. [Fig completion specs](https://fig.gitbook.io/fig/autocomplete) separate structured command models and dynamic generators from terminal presentation and keep the active specification loaded.

These systems show that rich completion presentation already belongs in the shell. Parsing, quoting, replacement ranges, and shell-specific semantics remain the hard parts of transporting an application model. The experiment asks only whether Wakterm's resident mux can serve that model with a small Zsh adapter and reliable fallback.

## Wakterm provides a concrete first provider

[Wakterm issue 41](https://github.com/wakamex/wakterm/issues/41) records duplicated command trees and growing static output. The current assets establish this baseline:

| Shell | Lines | Bytes |
|---|---:|---:|
| Bash | 5,264 | 181,104 |
| Fish | 448 | 85,246 |
| Zsh | 3,534 | 138,266 |
| Total | 9,246 | 404,616 |

The Zsh asset contains 266 command-context functions after the agent command tree was added. These counts establish generation and distribution cost, not a runtime performance result.

[`clap_complete::CompleteEnv`](https://docs.rs/clap_complete/latest/clap_complete/env/struct.CompleteEnv.html) generates a small shell wrapper that invokes a completer with command-line context. The engine builds candidates from the live Clap model, and its `completer` setting can direct the wrapper to a dedicated frontend instead of the application binary.

For Wakterm, that frontend can send requests to the existing mux server. This tests the resident case without creating a second daemon. A separate generic broker becomes justified only if another provider later needs a common lifecycle that the Wakterm mux should not own.

## Each provider owns cache identity and freshness

| Completion class | Safe cache identity | Freshness model |
|---|---|---|
| Command structure | Executable identity and version or content hash | Rebuild when the executable or exported schema changes |
| Dynamic values | Provider, arguments, working directory, selected environment, and configuration identity | Provider-specific expiry or invalidation |
| Filesystem paths | Directory and typed prefix | Prefer direct enumeration or filesystem-aware invalidation over broad persistent caching |
| Repository values | Repository identity, revision or state version, arguments, and typed prefix | Invalidate on relevant repository transitions |
| Remote and SSH values | Configuration, connection identity, authorization context, and typed prefix | Bound result age and invalidate configuration or connection changes |

The endpoint stores a result only when the provider supplies its cache key and freshness policy. Sensitive environment and authorization state are excluded from requests by default and included only when the provider contract requires them.

The first cache remains bounded and disposable. Nushell's current completion cache provides a useful minimum model: a bounded least-recently-used set keyed by text through the cursor and invalidated when the working directory, `PATH`, or available commands change. `wsh` does not copy those exact keys for every provider, but it requires an equally explicit identity and invalidation rule before storing a result.

## The protocol preserves replacement and display semantics

A request should carry provider and version, argument vector or token spans, cursor byte position, replacement range if known, working directory, shell, and only the environment values required by the provider. A response can carry candidate value, display text, description, group, type, suffix behavior, replacement range, ordering hints, and freshness metadata. Each request has a deadline and cancellation identity.

## Completion execution is bounded and cancellable

Dynamic completion runs on an editor hot path and must remain safe when a provider, filesystem, network mount, or command model behaves badly. Historical failures give the experiment concrete adversarial tests: [Fish once retained work after cancellation while enumerating six million files](https://github.com/fish-shell/fish-shell/issues/2771), and [a Nushell external-completer case repeatedly started Carapace processes until memory was exhausted](https://github.com/nushell/nushell/issues/13201). The accepted Wakterm path therefore requires:

- At most one active request for one provider and editor generation
- Cancellation as soon as the buffer, cursor, working directory, provider version, or relevant configuration changes
- Rejection of every response whose generation no longer matches
- A provider deadline and a separate bounded fallback deadline
- Maximum candidate count, response bytes, retained cache entries, and provider child processes
- No automatic retry loop within one Tab action
- Immediate native or static fallback when the endpoint is absent, incompatible, malformed, timed out, or over limit
- Trace events for queueing, provider startup, response time, cancellation, limit enforcement, cache identity, and fallback without recording the command line by default

Cancellation is complete only when provider work stops or is detached from further resource use under a separately measured supervisor policy. Ignoring a late response while an abandoned process continues scanning is not sufficient.

This does not provide automatic structured completion for arbitrary executables. A command needs a registered provider, an exported schema, a dynamic completion protocol, or a conventional Zsh completion function. Initial experiments cover Wakterm and `wsh`, where the project owns both sides and can validate requests against the real Clap parser.

`CompleteEnv` remains behind Clap's `unstable-dynamic` feature, its shell protocol can change, and its documentation recommends regenerating wrappers when an application is upgraded. The experiment therefore validates the generated wrapper and Wakterm version together. An accepted `wsh` adapter must fail back cleanly when the endpoint or protocol version does not match.

## The experiment tests whether residency pays for IPC

The first comparison tests:

1. Current static generation.
2. Static generation from a pruned command tree.
3. `CompleteEnv` through the direct Wakterm binary.
4. `CompleteEnv` through the existing Wakterm mux.

A separate generic broker is not part of this comparison. It requires a second application with an unresolved shared lifecycle need.

The comparison records installed bytes, Zsh function count, shell startup time with completion loaded, cold first-Tab latency, warm p50 and p95 latency over at least 100 requests, application startup and Clap parser-construction time, candidate correctness, a 50 ms provider timeout, mux-unavailable and malformed-response fallback latency, peak and retained memory, provider process count, cancellation latency, enforced result limits, and freshness. Golden cases include a top-level command, nested `agent request`, options, enum values, paths containing spaces, a cursor in the middle of an argument, a `--` command tail, the hidden `cli agent` compatibility route, SSH or other dynamic values, a configuration change between requests, a provider that never returns, a provider that ignores cancellation, and a provider that returns an oversized result. Candidate correctness is checked against the real Clap model rather than a duplicate fake.

The selection rule favors the smallest passing counterfactual. Use pruned static completion if it fixes the measured size problem without losing behavior. Otherwise use direct `CompleteEnv` if cold latency is acceptable. Use the existing mux only when application startup or parser construction dominates and the resident path passes timeout and fallback gates.

The mux path is accepted only if it preserves the tested candidate semantics, keeps fallback immediate when the endpoint is unavailable, and produces a concrete Wakterm improvement through lower measured latency, less generated structure, or both. A generic broker and generic cache remain unproven.
