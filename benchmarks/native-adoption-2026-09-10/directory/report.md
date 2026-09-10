# Directory persistence fixes pass; full native ownership remains a prototype

The C directory prototype now preserves integer and fractional rank formatting, applies last-record-wins duplicate updates, excludes canonical home paths, and keeps removal suppression consistent with prompt, directory-change and unload/reload hooks. Normal and ASan/UBSan runs pass 720 query comparisons, nine exact persistence comparisons, real lock timeout/recovery and mixed-writer tests, lifecycle/custom-command/unload checks, and actual ZLE completion. The tenth persistence comparison reveals a reference bug: the pinned Zsh implementation corrupts a tab-containing path when saving it, while the C implementation preserves it and successfully finds it afterward.

The ordinary lookup/write workloads pass their fixed performance gates. At 1,000 records, a complete fresh-shell lookup is 85.8% faster and a warmed broad lookup is 94.2% faster. These are separate workloads: the fresh-shell measurements include loading the source adapter and search for one `needle` record; warmed lookups exclude shell startup and plugin loading and match the `project` records.

| Workload | Records | Pinned Zsh median, ms | C prototype median, ms | Median reduction | Paired p95 change, ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Complete fresh-shell lookup | 100 | 12.396 | 5.049 | 59.3% | -7.223 |
| Complete fresh-shell write | 100 | 12.596 | 5.109 | 59.4% | -7.326 |
| Complete fresh-shell lookup | 1,000 | 61.646 | 8.736 | 85.8% | -52.005 |
| Complete fresh-shell write | 1,000 | 61.812 | 8.725 | 85.9% | -52.580 |
| Warm broad lookup | 100 | 7.041 | 0.458 | 93.5% | -6.465 |
| Warm broad lookup | 1,000 | 64.542 | 3.758 | 94.2% | -59.596 |

## Correctness changes

Rank updates now use Zsh's numeric type and formatting, retain unchanged rank text, and emit through the same associative-table ordering as the reference. Duplicate records contribute to the reference aging total but the last surviving record supplies the written value. Canonical home and excluded paths are checked after resolution. Removing the final record preserves the reference's empty-line output.

Two actual lifecycle regressions were reproduced before their fixes: a prompt immediately re-added a removed directory, and a subsequent unload/reload incorrectly retained suppression. The retained Zsh hooks now consult the C owner's removal state and clear it on directory changes and unload. The tests execute the real background writer and wait for its inherited output pipes to close rather than substituting a simulated writer.

The lock test holds the actual `zsystem flock` lock and checks both implementations return timeout status 2 without changing the database. Releasing the lock permits the next write. Twenty concurrent alternating Zsh/C writers produce the expected rank 22 from an initial rank 2. Tab round trips, custom `cd`, actual plugin unload and completion of ordinary and space-containing paths run against the pinned implementation and completion definition.

## Remaining adoption requirements

The full native owner remains disabled. Its whole-database removal branch still returns the prototype's unsupported-confirmation status, and its atomic rename path does not implement the reference's bind-mounted-datafile fallback. Those existing supported behaviors need implementation and direct regression tests before selecting the complete owner. The installed interactive-startup gate also remains outstanding for directory adoption. The cost measurements qualify the tested lookup/write paths, not those unimplemented behaviors or the complete installed feature.

The evidence supports further C consolidation. No additional ranking optimization is needed to justify that direction; the next work is the remaining compatibility behavior and installed qualification. The tab-path result should retain the correct native round trip rather than reproduce the reference's malformed database entry.

## Reproduction and retained evidence

All artifacts are unsigned host development experiments. `identity.json` records the source revision, source hashes, SDK header/configuration hashes, compiler, module and shell binary identities. `inputs.tar.gz` retains final sources, the exact pinned reference/completion bytes, and generated adapters. `results.tar.gz` retains inputs, before/after lifecycle failures, database bytes, normal/sanitized results, editor transcripts and all timing pairs.

Build the module with `cc -std=c17 -Wall -Wextra -Werror -O2 -fPIC -shared -I/var/tmp/wsh-native-tools/source-sanitized/Src -I/var/tmp/wsh-native-tools/source-sanitized native/directory-prototype.c -lm -o MODULE_DIRECTORY/wshdirectory.so`. Prepare adapters with `python3 native/prepare-directory-owner.py FIXTURE_DIRECTORY`. Use the recorded reference installation's `bin/wsh`, module directory, fixture directory and an absolute output directory as the four arguments to `native/test-directory-owner.py`, `native/test-directory-query.py`, `native/test-directory-persistence.py`, `native/test-directory-lifecycle.py`, and `native/test-directory-zle.py`.

Repeat correctness with the sanitized shell and a Clang module built using `-O1 -g -fsanitize=address,undefined -fno-sanitize=function -fno-omit-frame-pointer`, with `ASAN_OPTIONS=detect_leaks=0` and `UBSAN_OPTIONS=halt_on_error=1`. Final ordinary cost fixtures also pass the module comparison under sanitizers.

`native/measure-directory-owner.py` takes the same four arguments, with optional `correctness` for the pre-timing byte/status check. The timed mode runs 50 alternating pairs per operation and size with CPU 0 affinity, a fixed database clock, tracing off and database reset outside each timed operation. It checks matching command output and database bytes after every pair. `native/measure-directory-query.py` provides the warmed lookup comparison with source loading outside each timed span. The fixed lookup reduction gate is 20% at 1,000 records; the write regression gate is +3 ms paired p95. `benchmarks/verify-native-directory-adoption.py` verifies the retained identities, behavioral comparisons, sample counts and gate arithmetic while requiring the full owner to remain unselected in this result.
