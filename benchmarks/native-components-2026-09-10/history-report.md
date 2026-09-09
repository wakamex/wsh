# Native history navigation passes the bounded comparison

The native matching/navigation candidate improves the 10,000-entry default editing sequence by 11.0%, from 11.344 to 10.093 ms median. With duplicate filtering enabled, the same four-Up sequence improves by 73.1%, from 253.979 to 68.285 ms. Fifty alternating pairs per workload exercised actual ZLE with the normal highlighter present. All four workloads stay within the +1 ms paired p95 regression gate, and the duplicate-heavy target passes the 20% improvement gate.

| History and mode | Reference median | Candidate median | Reduction | Paired p95 change |
| --- | ---: | ---: | ---: | ---: |
| 100 entries, default navigation | 6.452 ms | 6.169 ms | 4.4% | +0.307 ms |
| 100 entries, unique navigation | 7.384 ms | 6.089 ms | 17.5% | -0.904 ms |
| 10,000 entries, default navigation | 11.344 ms | 10.093 ms | 11.0% | -0.909 ms |
| 10,000 entries, unique navigation | 253.979 ms | 68.285 ms | 73.1% | -179.765 ms |

Normal and sanitized tests passed 3,360 transitions across 32 configurations, plus 32 paired real-editor cases covering default, unique, fuzzy and vi modes, custom widgets, multiline movement and failed searches. The state corpus includes live history additions, prefix matching, literal pattern characters and case-sensitive/insensitive queries. Sanitized Zsh uses the previously documented leak/function-sanitizer exclusions. These tests compare buffer/navigation state; they do not establish complete highlight-region/cursor parity under every third-party widget wrapper.

The C prototype now owns pattern construction, history scanning, lazy duplicate filtering and navigation. It still exposes the plugin's internal parameters to retained Zsh editor/highlight adapters. The private fixture removes the original matching and navigation functions, but keeps the plugin's loading, multiline/native-history delegation and highlight lifetime behavior. That is a larger, measured ownership boundary than the earlier duplicate kernel, but it does not yet delete the complete plugin or its internal parameter interface. Keep it disabled pending that final ownership decision and broader composition qualification. Do not describe it as a selected complete C feature.

The corrected benchmark explicitly resets the previous-result marker between sequences. The excluded first run and its cause are retained in `history-measurement-audit.md`. The measured sequence includes typing, four Up widgets, highlighting and capture; it is not a single-widget latency or pure search-kernel measurement. No additional processes are introduced by the candidate.
