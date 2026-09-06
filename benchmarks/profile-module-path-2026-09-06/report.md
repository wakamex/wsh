# Installed profiling loads bundled modules

Profiling now configures the bundle module and completion paths before loading its adapter. The real-Zsh regression fails against official v0.3.0 with an empty fallback module path and passes against the corrected unsigned local bundle, including zprof loading and a written profile event. The complete profile privacy/report test, delayed ZLE-readiness test, and 19 retained-evidence verifiers also pass. User startup ordering is unchanged.

## Profiling overhead remains unresolved

The fresh 100-pair candidate run failed the unchanged 3 ms p90 overhead gate at 3.284 ms. A prior local bundle control passed at 2.525 ms; the second candidate run failed at 3.766 ms. Median paired overheads were 2.077, 1.980, and 1.829 ms respectively. The second candidate run included normal-start maxima of 60.133 ms and profile-start maxima of 53.528 ms; these outliers do not establish a cause. The first run overlapped retained-evidence verification, and the control/repeat sequence overlapped a short readiness test. These overlaps limit causal attribution and are retained rather than discarded.

After two failed candidate timing runs, the premise was audited: this change corrects a demonstrated relocation failure, while the existing instrumentation overhead is sensitive to timing variation. No additional timing intervention or passing performance claim is made. Controlled performance revalidation remains outstanding before release. Historical runtime tracing numbers in the combined gate output were not remeasured because runtime source and binary behavior are unchanged.

## Reproduction

`plan.md` fixes the hypothesis and threshold. `metadata.json` records the source, bundle manifest, binary identity, target, build configuration, workload and commands. `baseline.log` contains the official-bundle failure. `correctness.log` and `readiness.log` contain corrected correctness results. The samples, summaries, gate outputs and implementation diff preserve all three timing runs and their source change.
