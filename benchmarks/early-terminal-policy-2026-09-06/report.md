# Early completion respects Wsh terminal policy

Wsh now sets its default query policy before user .zshenv can initialize completion and load ZLE. The real-Zsh PTY regression emitted queries before the fix and suppresses them after it. All ten policy cases pass across login and non-login startup, including launch-environment opt-in, explicit user query enablement, explicit suppression, and preservation of other extension settings.

The same early-compinit fixture improved from 564.426 ms to 51.969 ms median first-editor readiness over five warm samples per bundle. All six baseline launches, including the retained cold start, emitted queries; none of the corrected launches did. This removes the unanswered-query wait in a PTY. A terminal that responds promptly can have a smaller latency difference.

## Verification and scope

The complete host bundle suite passed, covering the first commit's empty-module-path regression, end-to-end profiling, delayed readiness, shared configuration, editing, prompt selection, directory jumping, named themes, foreground job control and native terminal integration. All 19 existing retained-evidence verifiers passed. The canonical builder's Python 3.6.8 accepted the new test's syntax and subprocess arguments; the full canonical build, remote CI and two-build reproducibility were not rerun. The earlier profiling-overhead gate remains unresolved as documented in ../profile-module-path-2026-09-06/report.md.

The only production change is moving the existing terminal-policy block before user startup. The launch-environment opt-in remains supported. Users can replace .term.extensions explicitly in their startup files before loading ZLE. No installed bundle, live user startup file, or release tag was modified.

## Reproduction

The plan records the failure, intervention and pass condition. Metadata identifies both unsigned development bundles, source revision, manifest, manager and fixture. Baseline and candidate JSONL retain the cold start as iteration zero and five subsequent warm samples. The correctness log records all ten actual policy and query observations. The compressed host-suite log and evidence-check log retain broader verification.
