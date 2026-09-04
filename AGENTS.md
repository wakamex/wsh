# wsh repository instructions

Read [`DEVELOPMENT.md`](DEVELOPMENT.md) before changing implementation, benchmarks, release tooling, bundle layout, providers, renderers, themes, or performance-sensitive integration code.

- Build the smallest runnable local vertical slice before adding remote distribution, registry, or compatibility machinery.
- Record a reproducible baseline, an observable failure or cost, the cheapest counterfactual, and the passing threshold before implementing an intervention.
- Change one causal factor per experiment unless an interaction is the stated hypothesis.
- Keep Zsh integration as thin glue. Avoid per-byte or per-item interpreted shell loops when a whole-value Zsh builtin can perform the same transformation. Move repeated computation to Rust when doing so simplifies the boundary and preserves semantics, but test the smaller builtin counterfactual before adding a new native interface.
- Run correctness and adversarial tests before comparing performance.
- Identify every result by source revision, wsh bundle identity, Zsh source and binary identity, target, build configuration, enabled components, workload, fixture, trace mode, and benchmark command.
- Compare the same workload under the same instrumentation mode before and after a change, and measure instrumentation overhead separately.
- Mark every local bundle as an unsigned development artifact. A local build may be described as byte-identical to another build only when retained evidence proves it, but only immutable, attested GitHub Release assets are official releases.
- Treat an annotated `vMAJOR.MINOR.PATCH` tag push as deliberate release authorization. The `publish.yml` workflow builds twice from that tag, compares the canonical bytes, attests the agreed assets, and creates the immutable GitHub Release automatically. Never push a release tag unless the user explicitly authorizes that release.
- The main-push `release-eligibility.yml` workflow produces the `release-eligible / validate` check. Require that exact check on `v*` tags. The tag workflow must also find a successful main-push run for the exact tagged commit before building.
- Do not add a resident provider, native module, generic broker, database, remote updater, public directory backend, or compatibility framework without the evidence required by [`FEATURES.md`](FEATURES.md).
- When evidence invalidates a premise, replace the old design or plan instead of preserving contradictory paths.
- Preserve benchmark inputs, raw results, summaries, exact commands, and relevant hashes needed to reproduce an accepted claim.
- Before committing, run the relevant tests and benchmarks, run `git diff --check`, and report what was and was not exercised.
