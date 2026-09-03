# A pinned Zsh development revision must pass the stable bundle gates

Wsh currently builds the signed Zsh 5.9.2 source release. The product may describe itself as an edge Zsh distribution only after one exact upstream development revision passes the complete bundle's correctness, compatibility, resource, and performance gates against that stable baseline. This experiment pins upstream commit `cad0d67c76e2be7371cf3526b79ea2581810d35a`, observed at the canonical `zsh-users/zsh` `master` ref on 2026-09-03.

## Zsh 5.9 is the linear comparison point

The candidate contains 1,074 commits reachable from `master` after the Zsh 5.9 release commit. Zsh 5.9.2 was developed on a separate maintenance branch: the symmetric comparison has 481 commits unique to 5.9.2 and 1,074 unique to the candidate, including differently identified backports. Wsh therefore does not describe the candidate as a number of commits after 5.9.2.

The commit count is supporting revision context rather than a feature metric. Upstream [`NEWS`](https://github.com/zsh-users/zsh/blob/cad0d67c76e2be7371cf3526b79ea2581810d35a/NEWS) records the relevant user-visible development-line changes, including named references and namespaces, non-forking command substitutions, layered ZLE highlighting and named highlight groups, terminal capability reporting and cursor forms, monotonic high-resolution timing, completion changes, and job-control improvements.

## The source revision is the only build variable

The stable control and candidate use the same Wsh revision, x86-64 glibc 2.28 target, Rocky 8.10 builder and package lock, Rust and C toolchains, configure feature set, dependency boundary, locale, timezone, parallelism, source timestamp policy, archive normalization, enabled Wsh components, fixtures, and instrumentation mode. The source identity, versioned installation paths, and changes required to build that source are recorded before testing.

The experiment first makes the smallest build-script change needed to accept an explicit pinned Zsh source identity. It does not change Wsh integration behavior to accommodate a result until the unchanged candidate exposes a specific failure. Each subsequent intervention changes one causal factor and retains the failed precursor.

Stable source releases are authenticated with the upstream maintainer signature and archive digest. A development revision instead uses a committed source lock containing the canonical `zsh-users/zsh` repository URL, exact commit and tree identities, and the SHA-256 digest of the complete source snapshot. Build jobs resolve only that committed identity, reject a moving ref or changed snapshot, and bind the selected source to the resulting Wsh release through reproducible builds and build provenance. This proves which canonical upstream bytes Wsh selected; it does not claim that an unsigned development commit carries a Zsh maintainer signature.

The source lock's existence in a pushed Wsh commit authorizes that selection. The existing annotated Wsh release tag remains the single deliberate authorization to publish the complete release.

## Correctness precedes performance

The candidate passes only when:

- The source snapshot resolves to the pinned commit and its complete file digest is retained.
- The upstream Zsh suite passes with no candidate-only failure or broader exclusion.
- The complete glibc 2.28 bundle suite passes, including relocated startup, dependency and symbol checks, provider semantics, hostile values, cancellation, repainting, crash cleanup, job control, install, activation, and rollback.
- Existing `.zshrc`, changed `ZDOTDIR`, `RCS`, Oh My Zsh, theme, completion, and bundled-plugin coexistence fixtures pass unchanged.
- History substring search, autosuggestions, and syntax highlighting pass their individual and combined actual-ZLE fixtures.
- Targeted tests exercise the advertised development features selected for public wording. A feature is not listed on the front page merely because it appears in upstream `NEWS`.

Any changed default, compatibility break, terminal query, prompt escape, job-control transition, or plugin path is treated as a correctness result before its timing is considered.

## Paired measurements bound regression

Stable and candidate bundles run in alternating forward and reverse blocks on the same controlled host. Each workload uses the retained warmup and sample counts of its accepted benchmark, records raw samples, and identifies both Zsh binaries and bundle manifests.

The comparison includes:

- Raw Zsh process startup and first editable prompt.
- Complete Wsh startup through the first editable prompt.
- Clean, staged, modified, untracked, and detached-HEAD Git transitions under both renderers.
- Disabled, individual, and combined interactive-default startup, settled prompt, suggestion, acceptance, history navigation, short redraw, and 1,000-byte redraw workloads.
- Trace overhead, child-process counts, repaint counts, retained PSS, installed bytes, and compressed bundle bytes.

The candidate must pass every existing absolute Wsh gate. In the direct paired comparison, raw-Zsh and complete-Wsh first-editable p90 may each regress by at most 1.0 ms against 5.9.2. Existing provider, repaint, process, optional-lock, tracing, retained-memory, plugin startup, settled-prompt, and edit gates remain unchanged. The report records smaller differences without calling them improvements when they remain within measured run variation.

## Adoption requires tested user value

Passing compatibility alone makes the revision eligible, not necessary. Adoption also requires at least one named upstream capability that provides observable user value or measurably simplifies a Wsh integration. Public wording lists only those tested capabilities, followed by the exact pinned revision and the supporting 5.9-to-candidate commit count. Wsh remains on 5.9.2 if the candidate fails a gate, cannot satisfy the committed source-lock policy, or offers no tested benefit proportionate to development-line compatibility risk.
