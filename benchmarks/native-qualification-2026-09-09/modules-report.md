# Linked bundled modules preserve running-shell code across replacement

Native builds now link their configured bundled Zsh modules into the executable while retaining the dynamic loader for external modules. A running process successfully loads and reloads previously unused bundled modules after its executable is replaced and its module directory is deleted. A separately compiled module still loads and reloads. The upstream suite, 18 startup cases and all nine component contracts pass; the lifecycle and startup checks also pass under sanitizers.

| Comparison with dynamic bundled modules | Result |
|---|---|
| Existing-prompt startup median | 24.407 to 23.726 ms; paired p95 +0.294 ms, passing +3 ms limit |
| Minimal-prompt startup median | 25.093 to 24.422 ms; paired p95 -0.384 ms, passing +3 ms limit |
| Shell plus C-helper median PSS | 3,389 to 3,287 KiB |
| Largest paired PSS increase | -77 KiB, passing the 4,096 KiB limit |
| Executable size | 990,680 to 1,864,824 bytes |
| Required executable shared libraries | Same seven SONAMEs in both variants |

## Accepted build ownership

Zsh documents per-module static and dynamic linkage in `config.modules`. The native builder changes configured `link=dynamic` entries to `link=static` after configuration and retains the effective module configuration. Modules already disabled by platform configuration remain disabled. The default native source lock records this choice. Ordinary upstream builds keep their existing linkage.

This removes Wsh-owned module code from the running-shell package-lifetime problem without a resource-retention service or another activation system. External C modules still require a matching shell ABI, as before. Optional on-disk scripts, themes and helpers retain their own compatibility and graceful-failure requirements; this result does not promise arbitrary future compatibility for those resources.

The first `--disable-dynamic` counterfactual failed because it omitted required modules, including `zsh/stat`, and disabled external loading. Its failed upstream output and exact builder source remain archived. The selected candidate instead keeps the dynamic loader and links the configured bundled set. No custom module loader was introduced.

## Method and qualification

Start from `d2f6513`. Both performance variants use the same C helper bytes and corrected native startup. The candidate's private source lock records linked modules and its isolated output name; the selected default records the same linkage policy. Each prompt workload uses 50 alternating pairs on CPU 0 with native OSC readiness. Memory uses 20 alternating pairs, collecting `smaps_rollup` for the shell and its sole helper 100 ms after readiness. All samples are retained. The reported memory limit is checked against the maximum paired difference.

The old-inode test starts a real native executable, waits for its handshake, atomically replaces that pathname with the dynamic control executable, verifies `/proc/PID/exe` reports the deleted old inode, removes the private module tree, then requests bundled and external module loads and reloads. The same sequence passes with an instrumented linked core and separately instrumented external module. The configured upstream sanitizer exceptions disable leak detection and function sanitization; no diagnostics occur in these tests. Both Rust-helper and C-helper installations pass the full nine-component native contract runner, including real OMZ and foreground job control.

The archives retain effective module configuration, source/lock identities, commands, build logs, lifecycle outcomes, full contract logs, library lists and numerical inputs. Real RPM transactions on the final payload remain part of the remaining package qualification.
