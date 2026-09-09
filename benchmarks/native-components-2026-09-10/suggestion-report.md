# Native autosuggestion actions remain disabled

The larger native candidate reduces the measured 10,000-entry editing-and-acceptance sequence by 14.4%, from 7.269 to 6.225 ms median. It stays within the +1 ms paired p95 regression gate, but misses the 20% improvement threshold for this complete sequence. Keep the existing feature selected.

| History workload | Reference median | Candidate median | Reduction | Paired p95 change |
| --- | ---: | ---: | ---: | ---: |
| 100 entries, older-prefix fetch and acceptance | 5.671 ms | 5.481 ms | 3.3% | +0.100 ms |
| 10,000 entries, older-prefix fetch and acceptance | 7.269 ms | 6.225 ms | 14.4% | -0.797 ms |

The candidate combines the previously tested C history selector with native modify, suggest, clear, accept, partial-accept, execute and enable/disable/toggle actions. Actual ZLE comparisons passed in synchronous history, asynchronous history, vi, custom-strategy and real completion-strategy modes. The custom strategy test waits until an old request has started, replaces its buffer before the delayed response, and verifies the accepted replacement and absence of a later stale display. Normal and sanitized runs agree on the exercised buffer, cursor and suggestion states. Fifty alternating timing pairs at each history size use synchronous history selection to include the selection work in the measured editing sequence.

The async request/response machinery, strategy orchestration, highlight wrappers and widget registration remain the pinned Zsh implementation. Native actions call those functions through Zsh's own function API. This preserves their behavior in the tested cases but retains an internal interface and most lifecycle glue, so it does not establish complete C feature ownership. Broad arbitrary-widget compatibility, a complete native async lifecycle and process/resource bounds are not qualified by this experiment. No new process mechanism was added.

The earlier history-selection kernel speedup remains valid for that smaller boundary. This experiment shows why it cannot be quoted as the speedup of the full feature. Further consolidation needs a concrete design for removing the retained adapters and another full-feature comparison; selecting this partial port would add another owner without reaching that end state.
