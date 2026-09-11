# Git fallback extends native ownership with about 12 ms additional startup cost

Uncataloged upstream Git checkouts can now use native implementations while downloaded cataloged copies retain the fast path. The actual upstream autosuggestions v0.5.1 checkout passed installed ownership, display, acceptance, style and lifecycle checks under both prompt owners. Its median startup cost increased by about 12 ms compared with leaving that plugin external. Known catalog matches passed the existing 3 ms paired-p95 startup gate. The test used alternating runs of the baseline and candidate installations and measured the first editable OSC 133 marker.

| Startup workload and prompt owner | Baseline median, ms | Candidate median, ms | Paired-p95 additional time, ms | Result |
| --- | ---: | ---: | ---: | --- |
| One cataloged autosuggestions v0.7.0 copy, existing prompt | 19.780 | 19.747 | 0.225 | Pass, at most 3 ms |
| One cataloged autosuggestions v0.7.0 copy, Wsh minimal prompt | 20.344 | 20.259 | 0.127 | Pass, at most 3 ms |
| All five cataloged takeover components, existing prompt | 54.283 | 54.065 | 0.339 | Pass, at most 3 ms |
| All five cataloged takeover components, Wsh minimal prompt | 32.710 | 32.463 | 0.141 | Pass, at most 3 ms |
| Uncataloged upstream autosuggestions v0.5.1, existing prompt | 23.996 | 35.915 | 12.406 | Measured ownership tradeoff |
| Uncataloged upstream autosuggestions v0.5.1, Wsh minimal prompt | 25.759 | 37.735 | 12.298 | Measured ownership tradeoff |

## Selection and cost review

Select catalog-first recognition with local Git fallback. The user explicitly prefers native takeover of verified upstream copies even when native support temporarily lacks newer upstream features. Existing handoff safety and customization preservation remain required. Git checks occur during startup, with no new work on the editor path.

The matched direct comparison used the same v0.7.0 file, the same bundled Zsh interpreter and 50 alternating measurements in one shell. Catalog recognition took 0.961 ms median and Git verification took 15.030 ms median. This triggered the planned review above 10 ms. The cheapest counterfactual removed the per-command timeout wrappers; Git verification still took 12.462 ms, while allowing an unbounded wait on a stuck Git process. Reject that counterfactual. A persistent cache or native Git reader would add state or another implementation to optimize a path already avoided by cataloged snapshots. Retain the bounded fallback and add reviewed upstream snapshots to the fast-path catalog as relevant upstream files change.

Earlier diagnostic runs used the host Zsh while establishing the subprocess cost, including one run overlapping compilation. They are retained separately and do not supply the selected matched comparison. The direct verification comparison uses v0.7.0; the installed uncataloged startup comparison uses v0.5.1, so their durations do not measure the same workload.

## Correctness and provenance

The host and glibc 2.28 installation contracts pass all nine component suites, all 80 catalog handoffs, all 80 Git-fallback handoffs and 44 Git boundary cases. The boundary tests use real Git repositories and commands, covering unstaged, staged and committed relevant edits, assume-unchanged flags, replacement objects, unrelated local commits, disconnected history, missing references, fork-only remotes, HTTPS/SSH URLs, partial clones, filters/textconv, linked worktrees, symlinked checkouts, spaces and trailing newlines in paths, oversized remote configuration, missing/empty/oversized files, raw binary delimiters, both files of multi-file components, downloaded-file catalog matching and the remote-attempt bound. A sleeping Git executable supplements these real-Git tests to exercise the timeout.

The fallback matrix uses retained unchanged upstream implementations plus a fixture comment committed into temporary Git repositories, forcing a catalog miss without inventing a different implementation. It checks ownership, modified files, runtime overrides, active/disabled autosuggestions, explicit lifecycle opt-ins and actual editor behavior. The actual v0.5.1 checkout separately demonstrates an uncataloged historical release without fixture comments: commit `cbf0e24b1863c44606bbdd1edcb1c1b40efbcb55` was compared byte-for-byte with GitHub's immutable official file response. Both existing and Wsh prompt cases pass native ownership, legacy `zle-*` exclusion, configured style, suggestion display/acceptance and removal of temporary recognition helpers.

The local Git proof trusts normally fetched tracking references and configured official remote URLs; it does not authenticate user-forged Git metadata. Working files are compared with raw blobs from one common ancestor, independently of the index, Git filters and replacement objects. Partial clones are refused before object reads, remote configuration output is capped at 64 KiB, each Git command has a one-second timeout and 100 ms kill grace, and at most eight matching remotes are tried. A missing tool, reference or usable proof preserves external ownership.

## Build and measurement identity

Baseline source is `e84d5d3`, with unsigned host installation `ec4c3fe47f106a24e8ea10f318a74ed5deaf6a145da15c00e0f2d1f394251e2c`. The selected unsigned host installation is `30d848bfbfe58befc9d79843809da664a54f40beffd290b9ae477f9a4d0eb837`, built from `e84d5d3+dirty` with the source hashes in `identity.json`. Its native source lock, generated catalog, manifests, binary identities, build log, commands and raw results are retained in `evidence.tar.gz`. Native C source inputs are unchanged; the host native executable was rebuilt to carry the current compiled source identity and passed the upstream build suite.

Each startup workload has 50 alternating pairs per prompt owner, CPU 0 affinity, trace mode off, isolated HOME/ZDOTDIR and the same plugin source for both variants. Readiness requires native OSC 133 `B` and the primary editor marker. These are repeated startup measurements with naturally warm filesystem caches. No page-cache flush is claimed. The direct comparison times just the recognition calls using `EPOCHREALTIME`; the installed comparison includes process startup and the full first-prompt lifecycle. Existing disabled-tracing behavior and instrumentation modes are unchanged.

The floor test is an integration qualification on the previously accepted glibc 2.28 executable and runtime from installation `508db7f86035e60b65dde5d63220a7d62d6d80dc04fd9368daa51ffec397b38e`. The changed integration files and generated catalog were overlaid in a separate fixture, permissions and inventory were verified, and the original compiler/native identity was preserved with an explicit overlay revision. The floor container ran with networking disabled. This check did not rebuild the RPM or rerun sanitizer experiments; C source and package code did not change. Initial harness setup failures used an unpatched host reference, a container reference outside its mount, or an incomplete overlay inventory; corrected host and floor commands and their complete passing results are retained.

## Reproduction

Build with `CPPFLAGS=-I/var/tmp/wsh-native-sdk/usr/include LDFLAGS=-L/var/tmp/wsh-native-sdk/usr/lib64 WSH_ZSH_OUTPUT_ROOT=/var/tmp/wsh-git-provenance/zsh WSH_BUNDLE_OUTPUT_ROOT=/var/tmp/wsh-git-provenance/bundles WSH_BUILD_JOBS=4 ./build/build-native-installation.zsh`. These SDK paths identify this host's local development environment.

Run `python3 native/check-installation.py INSTALLATION OUTPUT` with `WSH_REFERENCE_ZSH` pointing to a host-usable pinned Zsh that includes the terminal marker patches. Run `python3 native/test-plugin-git-installed.py INSTALLATION UPSTREAM_CHECKOUT/zsh-autosuggestions.zsh OUTPUT` for the actual v0.5.1 checkout. `native/measure-older-autosuggestions.py BASELINE CANDIDATE OUTPUT` measures the single cataloged copy; adding the explicit v0.5.1 source path records the uncataloged startup tradeoff. `native/measure-plugin-catalog.py BASELINE CANDIDATE OUTPUT` measures all five cataloged components. `native/measure-plugin-recognition.zsh INSTALLATION CATALOGED_UPSTREAM_FILE` compares both recognizers against the same Git-backed file.
