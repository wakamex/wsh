# Explicit update command experiment

The experiment asks whether wsh can provide the conventional `wsh update` interface without adding network work to shell startup, weakening exact-release installation, or introducing another update protocol. The baseline launcher rejects `wsh update`, so users must edit a version twice inside a release-specific curl command.

## Smallest counterfactual

Reuse the existing immutable GitHub Release bootstrap as the only installation protocol. `wsh update --check` resolves GitHub's current immutable release without mutation, `wsh update --to vMAJOR.MINOR.PATCH` downloads and runs that exact release's bootstrap, and bare `wsh update` resolves the current release and applies it when newer. The command compares against the active verified release bundle so a user can update normally after rolling back while the external launcher remains newer.

The implementation uses the host `curl` and `sh` already required by the release bootstrap. It downloads the bootstrap to a private temporary directory instead of piping network bytes directly into a shell. No HTTP library, resident updater, registry, background check, startup hook, or package solver is added.

## Fixed correctness gates

1. `wsh update --check` reports whether a newer canonical release exists and never downloads or executes a bootstrap.
2. `wsh update --to vMAJOR.MINOR.PATCH` accepts only canonical stable release tags and constructs the exact GitHub Release asset URL.
3. Bare `wsh update` resolves the same authoritative latest-release redirect used by `--check` and applies only a newer release.
4. Same-version requests succeed without download, while an older requested or resolved version fails before download.
5. Latest-release redirects outside the exact `wakamex/wsh` tag path, malformed tags, failed downloads, and failed bootstrap execution fail closed.
6. A downloaded bootstrap is stored in a private temporary directory and removed after success or failure.
7. `--state-root` selects the active bundle used for comparison and is passed to the release bootstrap through `WSH_STATE_ROOT`.
8. Existing bootstrap digest, provenance, payload, activation, unsafe-destination, replacement, and rollback gates remain unchanged.
9. A live no-side-effect test checks GitHub's actual latest-release redirect and repository path.
10. Shell startup traces remain unchanged because update code runs only after the explicit `update` subcommand.

No prompt-performance threshold changes. The update command is an explicit network operation outside the measured startup path.
