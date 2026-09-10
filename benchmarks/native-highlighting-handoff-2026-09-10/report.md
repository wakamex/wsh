# Recognized upstream main-parser handoff

Recognized older upstream copies now use the installed C main parser while retaining their redraw lifecycle, styles and additional highlighters. Real ZLE ownership and editing tests pass for both upstream snapshots, modified implementations remain external, and the user's actual startup files produce identical tested colors in Wsh and regular Zsh. The final 50-pair startup comparison per prompt mode adds at most 2.421 ms at paired p95, passing the 3 ms gate.

| Prompt mode with older upstream main and brackets | Baseline median readiness | Native handoff median readiness | Paired p95 added readiness | Gate |
|---|---:|---:|---:|---:|
| Existing prompt | 21.309 ms | 23.177 ms | 2.421 ms | <= 3 ms, pass |
| Wsh minimal prompt | 22.484 ms | 24.289 ms | 2.339 ms | <= 3 ms, pass |

## Baseline and intervention

The user's unchanged upstream `0.8.0-alpha2-dev` highlighting plugin retained its interpreted parser under Wsh at baseline `f54df6f`. The existing pinned external-copy path also retained its parser. The intervention recognizes the pinned core/main pair and the older `b2c910a85ed84cb7e5108e7cb3406a2e825a858f` pair, then sources the installed native main adapter while keeping the existing lifecycle and optional highlighters.

## Acceptance gates

Before qualification, require native main ownership for both upstream pairs with active and pending hooks, unchanged configured styles and optional custom highlighters, and preserved modified main sources and runtime overrides. Exercise actual ZLE editing and regular Zsh with the user's startup files without editing those files. Compare the same older-plugin configuration under baseline and candidate instrumentation; paired readiness p95 must not regress by more than 3 ms. The gate isolates the highlighting integration using its real upstream files; full personal-configuration timing also includes unrelated NVM and SDKMAN initialization. The already qualified native parser remains unchanged. Allow two interventions at a failing gate before revisiting the hypothesis.

## Scope

Recognition uses exact core and main source contents and loaded main-function provenance. A version string alone never authorizes replacement. Additional upstream snapshots require retained source and regression coverage. Optional highlighters keep their own functions and settings. `external-exact` describes the retained external lifecycle; its main paint function invokes Wsh's native builtin. Main helper definitions remain available for custom highlighters that call them.

Custom optional highlighters still produce an `external-unknown` component finding so doctor does not suggest removing their installation. Their recognized main parser can use C independently.

## Verification

All nine host installation contracts pass, including real Oh My Zsh coexistence and doctor. The installed parser suite passes 3,360 prefix comparisons, composed ZLE region comparisons and 6,000 redraws with 0 KiB retained growth. Host upstream Zsh reports 75 successful scripts, zero failures and two skips. The canonical glibc 2.28 build also passes all nine installation contracts, parser checks, completion, history, directory, recovery, profiling, runtime lifecycle and RPM verification. Its upstream Zsh suite reports 75 successful scripts, zero failures and two skips. The C implementation is unchanged; its prior parser corpus and sanitizer qualification remains applicable.

The personal-configuration check uses the real `.zshenv` and `.zshrc` through a temporary ZDOTDIR observer, isolates history output and runs from a non-Git directory. Wsh reports an exact external lifecycle with native main; `/usr/bin/zsh` retains the original main parser. Quoted-command regions match, first-Tab completion works and Ctrl-C returns to the prompt. Both startup-file SHA-256 digests match the pre-test values. Private traces remain under `/var/tmp/wsh-highlight-handoff/user`; personal configuration is not included in the public evidence archive.

## Reproduction

`identity.json` records source digests, compiler, target, native executable and installation identity, and the exact build command. `evidence.tar.gz` retains the ownership result, installed parser results, all nine host contract logs, paired startup inputs/raw samples/summary, and canonical command and output. Run `zsh tests/syntax-highlighting.zsh INSTALLATION`, `python3 native/check-installation.py INSTALLATION OUTPUT` and `python3 native/measure-highlighting-handoff.py BASELINE_INSTALLATION CANDIDATE_INSTALLATION OUTPUT`. The measurement waits for native OSC 133 B with tracing off, pins CPU 0, alternates run order and keeps 50 pairs per prompt mode. Both installations load the same older upstream source files. All installations are unsigned development artifacts.
