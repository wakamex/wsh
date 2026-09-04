# Plugin doctor experiment

## Question and baseline

Can `wsh doctor` identify bundled-default declarations that are safe to remove without parsing or rewriting arbitrary `.zshrc` source and without adding diagnostic work to ordinary shell startup?

At Wsh commit `a63950e3382a231697ab9a1d57b724d1ee6b06ac`, `wsh doctor` exits 1 with the general usage message. The three existing adapters already classify implementations after normal user startup: exact history-search and pending autosuggestion copies are replaced, an exact active autosuggestion copy remains authoritative, exact syntax highlighting remains authoritative or is activated, and modified or unknown implementations remain external. These decisions are visible only inside the shell process.

A direct counterfactual launched the complete glibc 2.28 bundle `dfb97e003c22b89fda3c58e7b54ad1fcf9a566d548523bd9bea14f9057848666` as `zsh -dic` through the normal managed startup directory. An exact external autosuggestions declaration produced `WSH_AUTOSUGGESTIONS_OWNER=wsh` and `WSH_AUTOSUGGESTIONS_REPLACED=1`. This establishes that an opt-in diagnostic child can reuse the existing runtime classification without a source parser or new integration subsystem.

## Smallest intervention

Add `wsh doctor [--state-root <directory>]`. It launches the active bundled Zsh once with the same user-startup and bundle environment as `wsh`, asks a fixed command to write the existing ownership values to a private bounded report, applies a timeout, and prints only plugin-compatibility findings. Exact recognized copies receive a manual removal recommendation. Modified or unknown external implementations are described as preserved with no removal recommendation. The command never edits startup files.

The ordinary `wsh` and `wsh run` paths do not set diagnostic state, create a report, launch an additional process, read configuration, or change the Zsh adapters. A general health-check framework, static Zsh parser, configuration migration engine, machine-readable output, terminal diagnosis, and automatic repair remain outside this experiment.

## Fixed correctness gates

- `wsh doctor` succeeds for an active bundle and loads the applicable user `.zshrc` through the managed startup path.
- Clean configuration reports no redundant or unrecognized implementations.
- Exact upstream history substring search, exact Oh My Zsh history substring search, exact pending and active autosuggestions, and exact syntax highlighting receive a removal recommendation.
- Modified history search, autosuggestions, and syntax highlighting receive no removal recommendation and remain externally owned.
- Disabled Wsh defaults receive no removal recommendation even when their external implementations are loaded.
- Every tested `.zshrc` digest is unchanged after diagnosis.
- The existing plugin coexistence suites retain one runtime owner and preserve custom behavior.
- Missing diagnostic values from an older active bundle produce an explicit unsupported result rather than a false recommendation.
- Diagnostic execution is bounded to 10 seconds and a malformed report fails closed.

## Fixed startup gate

Build the baseline manager from commit `a63950e3382a231697ab9a1d57b724d1ee6b06ac` and the candidate manager with the same Rust 1.95.0 release profile. Run [`benchmark-first-editable.zsh`](benchmark-first-editable.zsh) against the same complete edge bundle with 5 warmups and 40 retained observations per variant. Candidate managed first-editable p90 may regress by at most 0.5 ms. Source inspection must also confirm that the ordinary launch branch performs no diagnostic file, child-process, or configuration work.

The first pilot inherited the host's live user configuration only in the managed variant, so it measured about 1.3 seconds of unrelated startup work and could not test the launcher change. The accepted rerun gives both managers the same isolated empty user `.zshrc`; the discarded raw samples remain beside the accepted inputs.

The baseline manager SHA-256 is `0b385580a60f58e2b827e2aa424598b5c2447c073d3339433eccca96775a62d9`. The bundle Zsh SHA-256 is `a902861ceae7cf1bc545fd0f3b0a3cfdb901c9d38e728886940e044de7efff48`.

## Stop limit

Allow two implementation attempts. If the existing ownership values cannot distinguish a required safe-removal case, record that case as unsupported rather than adding a Zsh parser or persistent diagnostic state. Stop after 90 minutes of implementation work or the second failed intervention and audit the premise before expanding scope.
