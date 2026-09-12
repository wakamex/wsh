# Jansson helper consolidation experiment

Question: can the existing system Jansson dependency replace vendored yyjson in the per-session helper with simpler maintenance and no meaningful user-facing regression?

Baseline: 8563422ea41cf595a47ac8169df8219787b973dc. Current yyjson helper sources and the installed native shell are unchanged. Candidate changes only helper JSON representation, decoding and encoding; theme parsing, Git collection, rendering and shell integration stay identical. Both helpers use the same compiler, flags and source snapshot.

The cheapest counterfactual is a directly linked Jansson helper, without a JSON compatibility layer, custom integer parser or protocol redesign. Current shell IDs/generations are signed Zsh integers. The prototype may reject integers above INT64_MAX; full-range differences must be recorded separately and prevent claiming exact protocol equivalence.

Correctness first: run both real helpers through lifecycle, cancellation, traces, bounds, malformed frames and the existing differential protocol corpus. Record every difference, including high unsigned integers and negative zero; require parity on representable ordinary shell requests and all four prompt themes. Run the candidate with ASan/UBSan before timing.

Performance gates fixed before implementation: 50 alternating pairs for Git refresh and native first-editable startup, paired p95 increase <= 3 ms for each workload; 20 alternating pairs for shell-plus-helper PSS, maximum increase <= 4 MiB. Also report paired ping round trips and executable size without turning either into a user-responsiveness claim. Trace-off comparisons use identical instrumentation; lifecycle tests cover live and buffered tracing. Reuse current benchmark workloads.

Stop after two failed interventions at a gate and audit the premise; at most two hours on this prototype before reporting an unresolved blocker. Do not change installed defaults or remove yyjson as part of this test. Retain candidate patch, exact commands, identities and raw results.
