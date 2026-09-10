# Native floor package and login checks pass

The native distribution builds and runs without Cargo or rustc. The canonical Rocky SDK passes both upstream Zsh suites, all nine native integration contracts, inventory tampering, recovery and profiling, 13 completion/editor cases, 110 history editor comparisons, directory ownership comparisons and 15 runtime lifecycle cases. The resulting `wsh` RPM installs through real DNF on Fedora 44. Serial getty/PAM login and job control pass; ordinary removal refuses while test accounts use Wsh and leaves their login working.

The SDK installs exact signed RPMs offline above the immutable base and verifies the full resulting package inventory. Every pinned download was fetched independently and matched its SHA-256. The SDK contains no Cargo or rustc. Native release staging accepts matching real RPM bytes and rejects altered bytes, inconsistent build records and extra product files. Workflow YAML parses locally. Actual GitHub publication is not exercised or authorized.

## Build and test changes

Native manifests and RPMs replace legacy launcher, installer and bootstrap release outputs. The exact-commit eligibility, independent worker comparison, attestation and immutable-release checks remain. VERSION supplies product identity. Integration contracts invoke native entrypoints directly. Historical evidence runs against its immutable pre-migration source tree, allowing subsequent crate removal without rewriting accepted measurements.

The autosuggestion contract previously waited for visible prompt text before Ctrl-C. Floor testing reproduced a cancellation timeout; waiting for OSC 133 editor readiness passes the same check. One retry reused a Git fixture with an already committed seed, and an earlier run encountered a script edited during execution. The final runner allocates fresh test output directories; the complete unchanged final run passes. Failed logs are retained beside the passing run.

This slice qualifies the build and package boundary. Two fresh exact-commit builds and expanded RPM transactions precede deletion of legacy crates in the next slice. No new timing claim is made because this change affects distribution and test orchestration. Runtime implementation bytes are unchanged.

Inputs, raw checks, source snapshots, package digest and VM evidence are in distribution-build.tar.gz and distribution-build-identity.json. The shared retained-evidence entrypoint verifies them.
