# Native release review: version labeling remains to qualify

Reviewed the 65 commits from published v0.3.1 (`950bde5`) through `b12185f`. The range contains the selected native shell, system-package distribution, complete native interactive owners and upstream recognition. The public RPM login check is fixed and passes the real container test. Detailed version output still needs its development/release labeling fix qualified before publication. The next release also needs final-tree package validation and a new version. The [release-note draft](release-notes/UNRELEASED.md) reflects the selected implementation without choosing a version.

## Confirmed findings

| Priority | Finding | Evidence and consequence | Required follow-up |
| --- | --- | --- | --- |
| Fixed | Public-install login test broke at the runner shell | The last step in `.github/workflows/publish.yml` nests `'''[[ $ZSH_VERSION == 5.* ]] && print WSH_LOGIN_OK'''` inside a single-quoted `bash -ec` script. Actual Bash parsing truncates the container script at `su -l wsh-test -c [[`, expands the version on the runner, and runs `print` on the runner. The probe exits 127. This job runs after immutable publication, so it must be fixed before a release tag | Quoted heredoc, interactive container stdin and explicit `util-linux` installation now pass YAML/Bash/Zsh regression tests and real Fedora RPM login; see [qualification](benchmarks/release-fixes-2026-09-10/public-login.md) |
| Medium | Native version output cannot distinguish a release build | `native/tools.c` unconditionally prints `(unsigned development artifact)`. `native/prepare-build.py` generates no build-status definition, even though release assembly sets `WSH_BUNDLE_STATUS=release`. A published binary would therefore still call itself a development artifact | Give version output accurate build-status wording while keeping authenticity verification separate; cover development and release-mode builds |
| Release preparation | Version and notes still identify the old distribution | `VERSION` and the native source lock still say `0.3.1`, and `release-notes/v0.3.1.md` correctly describes the already published legacy release | Select the next version separately, refresh its native lock and create its versioned notes from the reviewed draft; preserve historical notes |

The Bash reproduction replaces only the external `podman` executable with an argument recorder, leaving parsing to real Bash. No container, package transaction or GitHub mutation occurs. Extract the `Install and launch the public RPM` step with a YAML parser, retain its text from `podman run` onward, prepend `podman() { python3 -c 'import sys,json; print(json.dumps(sys.argv[1:]))' "$@"; }`, and execute that text with `bash -c`. The captured tail is `"bash", "-ec", "\n  dnf -y install /packages/*.rpm\n  useradd -m -s /usr/bin/wsh wsh-test\n  su -l wsh-test -c [[", "==", "5.*", "]]"`; stderr reports `print: command not found`. This proves the quoting failure independently of Podman or DNF behavior.

## Release scope and migration

| Area | Selected current behavior | Release-note treatment |
| --- | --- | --- |
| Shell and account login | Native Zsh entrypoint, linked bundled modules, system-owned executable, no per-user activation dependency | Lead with this change and the explicit account/PATH migration |
| Command interface | `--wsh-version`, `--wsh-doctor`, `--wsh-profile`, `--wsh-profile-report`, `--wsh-run`; ordinary Zsh argument semantics preserved | Include the migration table, especially `--version`, `--` and old manager subcommands |
| Distribution | x86-64 Fedora RPM, glibc 2.28 build floor, DNF ownership, no self-updater or hosted package repository | Explain that `wsh update` does not migrate legacy installations; do not imply general Linux package support |
| Implementation | C shell additions and one C helper per session; obsolete Rust crates/toolchain removed; Zsh remains the editor/language and retains selected lifecycle/configuration adapters | Describe consolidation and retained compatibility without claiming every file or plugin is C |
| Interactive components | Native compinit registration, history navigation, directory queries/persistence, complete autosuggestion controller and main highlighter | Include installed outcomes; automatic/deferred compinit initialization and approximate highlighting prototypes remain unselected |
| Plugin ownership | Catalog-first matching, bounded local Git fallback, modified/unverified implementations preserved, recognized Git-prompt hooks removed under Wsh prompt ownership | State native-first behavior and possible upstream feature lag, with the measured uncataloged startup cost |
| Zsh upstream work | Same pinned upstream commit as v0.3.1; new neutral-highlight ownership fix | Do not present the existing 1,074 upstream commits, OSC integration or zcompile fix as newly added in this release |
| Existing conveniences | `z`, four themes, prompt selection, suggestions, history search, highlighting and profiling already existed in v0.3.1 | Explain implementation and compatibility improvements rather than advertising these as newly introduced features |
| Maintenance automation | Daily upstream source check with ordinary GitHub Actions notifications | Document for maintainers; it does not add a user-side update process or change plugins automatically |

The release notes preserve the existing theme format, shared `.zshrc` use and optional OMZ loading. They explicitly describe system-package migration and the public command changes. Local `/etc/passwd` removal protection is described at its actual scope; remote identity directories and arbitrary shell-path aliases retain the migration guide's administrator checks.

## Documentation corrected during review

- README directory ownership now agrees with native takeover of recognized OMZ `z` copies.
- README separates the three upstream correctness fixes from native entrypoint, completion and highlighter implementation, removing the contradictory patch count.
- `native/README.md` no longer claims that assembly uses the deleted Rust manager.
- `NATIVE-PROGRESS.md` and the implementation plan now point to the selected completion and interactive owners, superseding their earlier partial-port status.
- Existing benchmark reports remain historical records of their measured revisions. Their earlier ownership statements are not rewritten to describe later implementations.

## Validation still required on the release candidate

The latest Git-fallback qualification passed nine host and nine glibc 2.28 integration suites, 80 catalog and 80 Git-fallback handoffs on each target, 44 Git boundary cases, actual uncataloged-upstream editor checks and matched startup gates. The floor run overlaid current integration on previously qualified binaries. Earlier work also retains complete canonical builds, sanitizers, package transactions and reproducibility results, each bound to its own revision.

After correcting the two defects, run the complete canonical build/package suite and two-build comparison on the final candidate. Validate the actual package with the intended user configuration. Main-push `release-eligible / validate` must pass on the exact selected commit before an authorized tag. The tag workflow then repeats validation, builds twice, attests and publishes, followed by public-artifact verification. This review does not substitute for those gates.

The review covered all commit subjects and the aggregate diff, current source locks and build selection, command handling, packaging/publication contracts, migration documentation and the retained reports supporting the release claims. It included the targeted Bash reproduction above. It was not a line-by-line audit of all 1,178 changed files or a new full package run.

## Commit disposition

The table accounts for the complete reviewed range. Prototype commits remain part of the development history; only the later installed selections define the shipped behavior.

| Commit | Change | Current disposition |
| --- | --- | --- |
| `9881e46` | Measure and reject eager native completion initialization | Evidence, documentation or rejected initialization experiment |
| `478628e` | Measure deferred completion startup and first-Tab latency | Evidence, documentation or rejected initialization experiment |
| `a097ec3` | Exclude generated Python bytecode from benchmark evidence | Evidence, documentation or rejected initialization experiment |
| `0967a73` | Attribute deferred completion first-use costs | Evidence, documentation or rejected initialization experiment |
| `a3d6c93` | Recover login-shell access when bundle startup fails | Historical launcher recovery, superseded by state-independent native startup |
| `ec7e9e9` | Compare native shell entrypoint with installation-owned launcher | Prototype/comparison retained; later installed selection determines shipped behavior |
| `4a29e8f` | Plan native Wsh implementation and staged C comparisons | Evidence, documentation or rejected initialization experiment |
| `c5066ce` | Document bundled Zsh correctness fixes in README | Evidence, documentation or rejected initialization experiment |
| `1abf1a9` | Add state-independent native version reporting and CLI boundaries | Selected implementation, integration or maintenance behavior |
| `577241d` | Implement native doctor with isolated startup and Zsh-owned cleanup | Selected implementation, integration or maintenance behavior |
| `4dafee9` | Run exact foreground argv through native Zsh startup and markers | Selected implementation, integration or maintenance behavior |
| `0f8bb8b` | Build native startup from locked inputs without user-state redirection | Selected implementation, integration or maintenance behavior |
| `c4ac10f` | Prototype native RPM with real Fedora login and transaction coverage | Prototype/comparison retained; later installed selection determines shipped behavior |
| `3f8b50d` | Implement native profile invocation and saved-report recovery | Selected implementation, integration or maintenance behavior |
| `3fa3951` | Capture native startup spans across early and noninteractive exit | Selected implementation, integration or maintenance behavior |
| `5205c70` | Keep native profile tracing local to its owning shell | Selected implementation, integration or maintenance behavior |
| `282331a` | Keep Git output cancellable until both process and pipe finish | Selected implementation, integration or maintenance behavior |
| `53f020a` | Prototype and measure a C Git collector at the existing helper boundary | Prototype/comparison retained; later installed selection determines shipped behavior |
| `f9e5fb3` | Prototype C theme validation with preserved TOML definitions | Prototype/comparison retained; later installed selection determines shipped behavior |
| `0a78686` | Prototype C rendering with exact prompt parity | Prototype/comparison retained; later installed selection determines shipped behavior |
| `412798d` | Prototype complete C runtime with bounded lifecycle and tracing | Prototype/comparison retained; later installed selection determines shipped behavior |
| `ba0f607` | Retain helper boundary after native child ownership experiment | Evidence, documentation or rejected initialization experiment |
| `1ca08c5` | Measure native completion scanning and retain bounded seed experiments | Prototype/comparison retained; later installed selection determines shipped behavior |
| `546b221` | Prototype native directory matching with measured query parity | Prototype/comparison retained; later installed selection determines shipped behavior |
| `4cf9d07` | Compare native lazy history filtering against real history records | Prototype/comparison retained; later installed selection determines shipped behavior |
| `caceaaa` | Compare native autosuggestion history selection and builtin quoting | Prototype/comparison retained; later installed selection determines shipped behavior |
| `20da944` | Retain rejected native highlight classifier after full redraw comparison | Prototype/comparison retained; later installed selection determines shipped behavior |
| `d2f6513` | Keep relocated native resources independent of the build tree | Selected implementation, integration or maintenance behavior |
| `aa4f0d2` | Link bundled native modules while preserving external module loading | Selected implementation, integration or maintenance behavior |
| `a98029e` | Select the tested C runtime for native installations | Selected implementation, integration or maintenance behavior |
| `1064e43` | Make native RPM assembly reproducible and qualify final login behavior | Selected implementation, integration or maintenance behavior |
| `e957101` | Document and verify native command and account migration | Selected implementation, integration or maintenance behavior |
| `746a441` | Qualify reproducible native floor builds and installed RPMs | Evidence, documentation or rejected initialization experiment |
| `6d8d9ff` | Finalize native qualification inventory and retained decisions | Evidence, documentation or rejected initialization experiment |
| `eae1185` | Retain complete directory owner prototype and compatibility findings | Prototype/comparison retained; later installed selection determines shipped behavior |
| `768791e` | Compare native history navigation in default and unique editor modes | Prototype/comparison retained; later installed selection determines shipped behavior |
| `a881cc8` | Retain native autosuggestion action comparison and async compatibility tests | Prototype/comparison retained; later installed selection determines shipped behavior |
| `64e639b` | Retain native completion scan with passing cache and first-Tab gates | Prototype/comparison retained; later installed selection determines shipped behavior |
| `d4c07fe` | Attribute highlighting cost and verify all five component experiments | Evidence, documentation or rejected initialization experiment |
| `799e1d6` | Integrate measured native completion registration with safe callback lifetime | Selected implementation, integration or maintenance behavior |
| `6f21a1b` | Select native history ownership after installed editor and startup qualification | Selected implementation, integration or maintenance behavior |
| `07f91c7` | Repair native directory persistence and qualify query and lifecycle comparisons | Selected implementation, integration or maintenance behavior |
| `aca3cf2` | Preserve directory database confirmation before locking | Selected implementation, integration or maintenance behavior |
| `b5425ff` | Preserve bind-mounted directory databases during native updates | Selected implementation, integration or maintenance behavior |
| `625c7f2` | Select native directory ownership after installed compatibility and startup gates | Selected implementation, integration or maintenance behavior |
| `1cf156c` | Qualify combined native components on the glibc 2.28 floor | Evidence, documentation or rejected initialization experiment |
| `abece21` | Build and verify native installations without Rust tooling | Selected implementation, integration or maintenance behavior |
| `4cb80d5` | Migrate native RPM builds and release preparation off Rust | Selected implementation, integration or maintenance behavior |
| `ebe2b4c` | Use the resolved source timestamp when packaging isolated worktrees | Selected implementation, integration or maintenance behavior |
| `32d2bc6` | Retire obsolete Rust distribution after native package qualification | Selected implementation, integration or maintenance behavior |
| `e28e8db` | Verify the canonical native build after Rust source removal | Evidence, documentation or rejected initialization experiment |
| `76e7ca4` | Prototype complete native autosuggestion controller ownership | Prototype/comparison retained; later installed selection determines shipped behavior |
| `3fcad96` | Prototype native highlighting parser and retain compatibility failures | Prototype/comparison retained; later installed selection determines shipped behavior |
| `c78fbf4` | Adopt native autosuggestions after installed and floor qualification | Selected implementation, integration or maintenance behavior |
| `ab1691c` | Preserve neutral highlight ownership metadata in bundled Zsh | Selected implementation, integration or maintenance behavior |
| `2d3b2d3` | Retain faithful highlighting traversal comparison without adopting it | Prototype/comparison retained; later installed selection determines shipped behavior |
| `b9a8664` | Qualify complete native main highlighting against upstream and real ZLE | Evidence, documentation or rejected initialization experiment |
| `f54df6f` | Select complete native main highlighting after installed qualification | Selected implementation, integration or maintenance behavior |
| `1f9c258` | Upgrade recognized upstream highlighting copies to native main | Selected implementation, integration or maintenance behavior |
| `9a5c703` | Deactivate recognized git-prompt hooks under Wsh prompt ownership | Selected implementation, integration or maintenance behavior |
| `7bbee20` | Take native ownership of recognized upstream directory jumping | Selected implementation, integration or maintenance behavior |
| `3d63e23` | Recognize upstream v0.7.0 autosuggestions for native ownership | Selected implementation, integration or maintenance behavior |
| `e84d5d3` | Catalog upstream plugin snapshots and qualify shared native handoffs | Selected implementation, integration or maintenance behavior |
| `4a94e99` | Recognize uncataloged upstream plugins through bounded local Git proof | Selected implementation, integration or maintenance behavior |
| `b12185f` | Check upstream plugin changes daily with GitHub Actions | Selected implementation, integration or maintenance behavior |
