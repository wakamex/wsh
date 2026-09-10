# Combined native components pass glibc 2.28 qualification

Commit 625c7f2 passes the native and canonical legacy glibc 2.28 build paths. The native installation passes 17 suites, including all nine installed compatibility contracts, completion registration and actual Tab behavior, 110 history editor comparisons, 720 directory query comparisons, persistence, confirmation, lifecycle, profiling, recovery, and runtime protocol checks. Additional runs pass 14 startup/state/relocation cases and actual writable/read-only file bind mounts. The canonical legacy suite completes its relocated-bundle, login recovery, job-control, dependency-floor and archive checks.

| Artifact | Identity | Newest imported glibc version |
| --- | --- | --- |
| Native development installation | 1e169a7972279428b3728d4b21af12bb7cbb7635450673b0b8d9b64f5e604c26 | Shell: 2.25; C helper: 2.17 |
| Canonical legacy development bundle | 52def048e8edd3f06e9d40fb26015dca0bc66d7b4e33a6d4c1223bf8078c2d2f | Complete payload and tools: 2.28 |

## Build and test scope

Both builds use fresh detached worktrees at the same source commit, separate build and Cargo directories, locked Zsh and Rust inputs, and fixed source epoch and environment. Native testing uses the previously qualified local SDK image sha256:5da32743ab3b62bd8ebf0e67580d32512733e2a5e8b09f2f1b45d199ef7f5dd8, which extends the pinned canonical Rocky builder with the recorded native dependencies. The canonical legacy path uses the unchanged public builder digest. These are unsigned local development artifacts. This experiment runs one build of each artifact contract.

The native build passes upstream Zsh's suite. Installed tests use the real pinned reference implementations, the actual Oh My Zsh checkout, and a proper container init. The additional startup run covers missing/corrupt/unreadable state, shell startup context and options, missing HOME, non-UTF-8 relocation, early modules, symlink invocation, and unavailable optional integration. Four global-startup cases require bwrap, which this SDK lacks; those passed on the host in the installed qualification and are explicitly omitted from the additional floor harness. The complete floor recovery suite still passes.

The first installed floor run mounted the reference Zsh away from its compiled module prefix, causing module-loading failures before the product checks. Restoring that reference mount at its compiled path passes the unchanged tests. The first additional startup run stopped at the unavailable bwrap command. Both failed logs, the scoped startup harness, actual container arguments, source snapshots, manifests, ELF version records, raw test results, and canonical archive digest are retained in floor.tar.gz and floor-identity.json. No product change was needed for floor qualification.
