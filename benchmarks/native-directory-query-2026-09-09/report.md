# Native directory matching cuts 1,000-entry lookup from 45.15 to 17.04 ms

The private C matching kernel reduces median warm directory lookup by 62.25% at 1,000 entries and 58.79% at 100 entries. The comparison holds database reading, filtering, persistence and output in the pinned Zsh-z implementation and replaces its matching/ranking loop. Both implementations pass 720 output comparisons, including case modes, rank/time/frecency, trailing slashes, missing and kept paths, Unicode, shell metacharacters and completion output. Custom-command and persistence checks also pass, including the sanitizer run.

| Real directory entries | Reference median | C kernel median | Median reduction | Paired p95 change |
|---|---:|---:|---:|---:|
| 100 | 5.091 ms | 2.098 ms | 58.79% | -2.921 ms |
| 1,000 | 45.146 ms | 17.043 ms | 62.25% | -27.709 ms |

## Retain the partial port for a decision

The fixed gates pass: at least 20% median reduction at 1,000 entries and no more than +3 ms paired p95 regression. Keep the prototype available, with the existing implementation still selected. The native function consumes dynamic locals from the existing Zsh-z function and returns its associative arrays and winning paths. This avoids duplicating Zsh pattern, case-conversion and arithmetic semantics, but couples the replacement to both the plugin's internal function and the Zsh module ABI. Most of the 1,890-line upstream component remains responsible for persistence, directory changes, hooks, configuration and completion. No upstream dependency or production code has been deleted.

Adoption therefore needs a choice between this measured lookup improvement and the added partial-port interface, or a separately bounded complete directory-component port. The existing default does not automatically load this module. No user configuration or history was modified.

## Method and retained inputs

The baseline revision is `1ca08c5`, using the unsigned native C-helper installation identified in metadata. Its Zsh binary is unchanged. Each size uses 50 alternating warm pairs on CPU 0 in one shell. Sourcing each implementation occurs outside the measured lookup. Both variants receive the same fixed clock through an identical test-only substitution. Raw elapsed values come from Zsh's `EPOCHREALTIME`, with output buffered outside measured spans; the paired p95 is the 48th sorted difference out of 50. Initial baseline samples and final matched samples are retained separately. These are lookup measurements, not editor-readiness or database-write latency claims.

The final release and sanitized variants each pass the complete 720-case matrix and custom-command/persistence checks. The sanitizer module uses AddressSanitizer and UndefinedBehaviorSanitizer against the already instrumented native Zsh. Leak detection and the function sanitizer remain disabled for the documented upstream host boundaries; the standalone C runtime's stricter sanitizer evidence remains separate. No sanitizer diagnostics occurred. Database bytes stay unchanged during read-only queries. Existing production ZLE and OMZ evidence is unchanged; this partial prototype has not received a separate full ZLE adoption qualification.

Malformed database lines are filtered by the retained loader. The C kernel additionally requires numeric fields before invoking arithmetic. Delimiter-ambiguous paths and extreme arithmetic inputs have not established full migration parity and remain outside the adoption claim. Build commands, generated reference/candidate sources, configured Zsh headers, fixture scripts, raw outputs, source and binary identities are retained in the archives. The verifier reconstructs the numerical gates and checks the exact comparison outputs.
