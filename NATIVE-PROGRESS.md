# Native migration execution

The active goal is to work through all ten stages of [NATIVE-IMPLEMENTATION-PLAN.md](NATIVE-IMPLEMENTATION-PLAN.md), commit independently, finalize passing improvements, and retain decision-dependent prototypes for discussion. No push, publication, or live account-shell change is included.

| Stage | Status | Evidence or next action |
|---|---|---|
| 1. Native tools | Complete in locked native build | Version and doctor pass. [Version](benchmarks/native-tools-2026-09-08/report.md), [doctor](benchmarks/native-doctor-2026-09-08/report.md) |
| 2. Native startup and foreground | Complete in locked native build | [Foreground action](benchmarks/native-foreground-2026-09-08/report.md) and [startup/build comparison](benchmarks/native-build-2026-09-08/report.md) pass |
| 3. System package and login | Tested RPM prototype; policy decisions retained | [Real Fedora PAM, SELinux, reboot and package tests pass](benchmarks/native-package-2026-09-08/report.md); cross-ABI upgrade and supported removal policy remain open |
| 4. Profiling | Native path passes; report migration decisions retained | [Invocation and reporting](benchmarks/native-profile-2026-09-08/report.md), [startup recovery](benchmarks/native-lifecycle-2026-09-08/report.md), and [child isolation](benchmarks/native-profile-isolation-2026-09-08/report.md) pass; shell-owned component/function callbacks remain counted |
| 5. C Git collector | Tested opt-in C prototype; default remains Rust | [Correctness and resource gates pass](benchmarks/native-git-2026-09-08/report.md); C plus temporary bridge adds code, so full runtime comparison is next |
| 6. C themes and rendering | Pending | Preserve definition and rendering behavior before simplification |
| 7. Runtime process boundary | Pending | Compare the same C functionality |
| 8. Completion | Pending | Audit, scan, dump and first-use cost |
| 9. Interactive components | Pending | Independent directory/history/suggestion/highlighting comparisons |
| 10. Migration and qualification | Pending | Consumer inventory, local qualification, decisions and verification limits |

Each result is bounded by its predeclared experiment gates. A retained prototype is not an adopted production implementation. Production currently remains on the existing Rust-manager bundle path.
