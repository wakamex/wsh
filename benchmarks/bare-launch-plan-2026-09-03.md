# Bare wsh launch experiment

The installed `v0.1.3` launcher prints usage and exits when invoked as `wsh`, even though starting the active shell is the command's primary operation. `wsh run` launches correctly, but requiring the subcommand adds friction to every interactive start.

The smallest counterfactual is CLI dispatch only: treat an empty argument list as the existing `run` path. Keep `wsh run` as the explicit scriptable form, keep shell arguments behind `wsh run --`, and leave every named subcommand unchanged.

The intervention passes when bare `wsh` selects the active bundle, replaces itself with the same bundled Zsh as `wsh run`, and reaches the existing prompt path. The floor test must verify process replacement for both forms, and the existing Rust, bundle, PTY, portability, and startup gates must continue to pass. The dispatch adds no process, file read, network request, parsing layer, or persistent state.

Make one dispatch-only attempt. If the empty invocation cannot reuse the exact run implementation, stop and refactor the common launch path rather than maintaining two launch behaviors.
