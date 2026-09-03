# Autosuggestions should become a measured Wsh default with bounded widget ownership

The accepted history-search bundle `5892d1f976cd256df49efa011328bed3b5e4f32352aba1482d9553850f53f3f3` has no autosuggestion layer unless user configuration loads executable code. This experiment isolates `zsh-users/zsh-autosuggestions` commit `85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5`, first as an ordinary `.zshrc` plugin and then as a trusted bundle component.

## The first counterfactual pins the established implementation

Wsh retains the exact upstream distribution file and license, compiles it with the bundled Zsh, and loads it after history substring search. Its documented variables remain caller-configurable. A normal external copy registers `_zsh_autosuggest_start` for the first `precmd`; before that hook runs, Wsh can recognize the exact bounded source, remove its pending hook, and load the bundled copy. A modified implementation or a copy that has already wrapped widgets remains the sole external owner. Wsh does not attempt to unwind arbitrary widget wrapper stacks.

Upstream rebinding scans and wraps eligible ZLE widgets at every prompt and describes that behavior as a material performance cost. The cheapest optimization sets its documented `ZSH_AUTOSUGGEST_MANUAL_REBIND` mode before bundled startup, after user `.zshrc` widgets and the Wsh history widgets exist. Correctness fixtures must show that the first bind includes those widgets, existing user widgets still run, syntax highlighting composes, and a focused explicit rebind incorporates a later widget. A failure retains upstream automatic rebinding rather than adding a new widget broker.

## Correctness gates exercise the visible suggestion lifecycle

The candidate passes only when:

- Typing a prefix produces the expected history suffix in `POSTDISPLAY`, accepting it produces the complete buffer, and ordinary editing clears or refreshes the suggestion.
- Rapid edits and Ctrl-C do not leave an asynchronous child, descriptor handler, or suggestion behind.
- History search clears autosuggestion state and continues to navigate older and newer matches.
- The documented style, strategy, widget lists, ignore pattern, buffer limit, asynchronous mode, and manual-rebind setting remain configurable.
- A recognized not-yet-started upstream copy becomes Wsh-owned with one pending start hook; a modified or already-started copy remains external without another bundled load.
- An unrelated custom widget remains functional, and an explicit disable setting loads no bundled autosuggestion widgets.
- The pinned syntax-highlighting implementation remains active and its redraw hooks remain singular in the supported load order.

## Performance gates cover startup, repeated prompts, and editing

Startup uses 5 warmups followed by 20 forward-order and 20 reverse-order launches pinned to CPU 0. The clean bundled default may add at most 1 ms p90 over loading the same upstream component through `.zshrc`. Recognized takeover may add at most 4 ms p90 over the pre-change external path. The disabled adapter may add at most 0.25 ms p90 over the accepted history-only baseline.

A single-shell prompt benchmark records at least 100 no-op command transitions after warmup. Manual rebinding is accepted only if its p90 improves by at least 20 percent over upstream automatic rebinding and no correctness fixture requires repeated implicit scanning. Suggestion availability and full acceptance each use at least 100 warm history-prefix interactions; candidate p90 may be no more than 20 percent slower than the upstream path. One edit may fork at most one asynchronous Zsh worker, cancellation must reap it, and neither startup nor editing may execute a comparison helper or another utility.

The direct pinned implementation and documented manual-rebind counterfactual are the two planned paths. A failure requires revisiting the ownership boundary or leaving autosuggestions external before adding a native widget layer, resident service, or general ZLE composition framework.
