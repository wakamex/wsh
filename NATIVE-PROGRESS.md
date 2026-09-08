# Native migration execution

The active goal is to work through all ten stages of [NATIVE-IMPLEMENTATION-PLAN.md](NATIVE-IMPLEMENTATION-PLAN.md), commit independently, finalize passing improvements, and retain decision-dependent prototypes for discussion. No push, publication, or live account-shell change is included.

| Stage | Status | Evidence or next action |
|---|---|---|
| 1. Native tools | In progress | Native version slice passes; doctor next. [Evidence](benchmarks/native-tools-2026-09-08/report.md) |
| 2. Native startup and foreground | Pending | Integrate accepted startup prototype and explicit foreground interface |
| 3. System package and login | Pending | Real RPM and disposable VM transactions/accounts |
| 4. Profiling | Pending | Native lifecycle and report comparison |
| 5. C Git collector | Pending | Hold helper boundary fixed |
| 6. C themes and rendering | Pending | Preserve definition and rendering behavior before simplification |
| 7. Runtime process boundary | Pending | Compare the same C functionality |
| 8. Completion | Pending | Audit, scan, dump and first-use cost |
| 9. Interactive components | Pending | Independent directory/history/suggestion/highlighting comparisons |
| 10. Migration and qualification | Pending | Consumer inventory, local qualification, decisions and verification limits |

Each result is bounded by its predeclared experiment gates. A retained prototype is not an adopted production implementation. Production currently remains on the existing Rust-manager bundle path.
