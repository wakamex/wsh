# Native registration scanning passes the startup and first-Tab gates

The full C registration scan reduces cold startup p95 from 153.2 to 125.2 ms. Relative to the 26.0 ms no-compinit baseline, cold, stale and unusable-cache overheads are 99.2, 97.6 and 98.0 ms, all within the fixed 100 ms budget. First Tab stays near 72 ms p95. Fifty alternating samples per owner and cache state exercised actual Git completion through ZLE.

| Cache state | Reference startup p95 | Native startup p95 | Native overhead over baseline | Native first Tab p95 | Native second Tab p95 | Startup budget |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Missing dump | 153.209 ms | 125.240 ms | 99.237 ms | 71.997 ms | 25.580 ms | 100 ms |
| Reusable dump | 38.260 ms | 38.431 ms | 12.427 ms | 72.005 ms | 25.064 ms | 20 ms |
| Stale dump | 154.717 ms | 123.577 ms | 97.574 ms | 72.100 ms | 25.024 ms | 100 ms |
| Unusable dump directory | 153.498 ms | 123.994 ms | 97.990 ms | 71.586 ms | 25.218 ms | 100 ms |

The cold result has only 0.763 ms of margin. This is a passing controlled-host prototype, not a guarantee about other hosts or configurations. It remains disabled pending installation integration, a check of that final artifact, and a decision about maintaining the small private compinit interface.

The first intervention replaced only ordinary ASCII header reads with one bounded C read. All other headers fell back to the actual Zsh reader. It passed 2,017 header comparisons and normal/sanitized cache and editor tests, but cold/stale/unusable overhead remained 110-112 ms, failing the gate. The second intervention moved directory enumeration, duplicate suppression and registration dispatch into C. It continues to call Zsh's actual compdef and autoload behavior, with two private shell adapters for exceptional header reads and autoload. Compinit still owns compaudit, insecure-file exclusions, dump validity, dump generation and widget setup. No audit bypass or completion broker was added.

Both normal and sanitized full-scan runs passed nine real compinit dump/mapping cases, 13 actual ZLE cache/completion/composition cases, and additional authoritative-parser cases covering custom registration flags, long/binary/non-ASCII headers, special filenames, duplicate priority and explicit security refusal. Diagnostics from the autoload adapter are compared after normalizing its function-name prefix. Cancellation and bounds of actual candidate generation are unchanged by this scanner and were not separately requalified here.

The retained archive contains both interventions, raw 450-shell timing samples for each, transcripts, effective startup configurations, cache fixtures and correctness results. The full scanner's C source is shared with the bounded header test. It has not been connected to the native source lock, packaging or selected startup path. Selecting it should bind the change to the bundled compinit version and test the installed integration; unknown user-supplied compinit functions should retain their own behavior.
