# Startup cost of the interactive defaults and automatic completion

Wsh now applies interactive defaults before user startup files and sets up completion when those files did not. This measurement asks what that costs at startup, and whether a user who removes [Oh My Zsh (OMZ)](https://ohmyz.sh/) starts as fast as before.

Result: a shell whose startup files set up no completion starts 15.4 ms slower, because it now has completion; that is the same cost as a startup file that runs `compinit` itself. Every other case is unchanged within 1 ms, and Wsh with an empty `.zshrc` starts in less than half the time of the same shell loading OMZ.

Each case started interactive Wsh in a pseudo-terminal 100 times and measured the shell's own CPU time until the first editable prompt, alternating the two builds and four startup files in every round.

## Results

Median CPU time to the first editable prompt, in milliseconds; lower is better. "Before" is the build without the defaults and "after" the build with them.

| Startup file | Before | After | Change |
| --- | ---: | ---: | ---: |
| Empty `.zshrc` | 18.970 | 34.369 | 15.399 slower; completion is now set up |
| `.zshrc` that runs `compinit` | 34.666 | 33.964 | 0.702 faster |
| `.zshrc` that loads OMZ with no plugins or theme | 75.838 | 75.027 | 0.811 faster |
| `.zshrc` with `WSH_DISABLE_COMPLETION=1` | 18.788 | 18.640 | 0.148 faster |

The 95th percentiles follow the medians: 20.916 to 38.382 ms for the empty file, 38.123 to 37.935 ms with `compinit`, 81.776 to 79.297 ms with OMZ and 21.140 to 20.858 ms with completion off. [summary.txt](summary.txt) has every figure and [results.json](results.json) every sample.

The defaults themselves cost nothing measurable: with completion turned off, the build with them is 0.148 ms faster. The history-search key bindings now use one subshell where they used four, which offsets the new settings.

## Method

[measure.py](measure.py) starts `wsh -di` under a new pseudo-terminal with `HOME` and `ZDOTDIR` set to a directory holding only the `.zshrc` under test, waits for the prompt marker `OSC 133;B`, kills the shell and reads its CPU time from `wait4`. The environment is `PATH=/usr/bin:/bin`, `TERM=xterm-256color`, `LC_ALL=C.UTF-8`, an empty `WSH_THEME` and `LS_COLORS=di=01;34`, so no `dircolors` process runs. Three unmeasured starts per case write the completion dump and warm the file cache.

CPU time is the reported figure because the host was running unrelated work during the run (load average 8.61); wall-clock medians are in the same files and agree within 1 ms except for OMZ, whose wall time is lower than its CPU time because it runs helper work in parallel.

```sh
python3 benchmarks/interactive-defaults-2026-10-12/measure.py ~/.oh-my-zsh /var/tmp/wsh-defaults-clean 100 \
  before=BEFORE/bin/wsh after=AFTER/bin/wsh
```

## Identity

Both builds are unsigned development installations produced by `./build/build-native-installation.zsh` from clean checkouts on Fedora 44 x86-64 (AMD Ryzen 9 3950X), target `x86_64-redhat-linux`, Wsh version 0.4.6, pinned Zsh source `cad0d67c`.

| Build | Source revision | Native source lock SHA-256 | `bin/wsh` SHA-256 |
| --- | --- | --- | --- |
| Before | `d43d04265ca2fbbfbb6104090a923cf68f638b08` | `a301ce8b7714fc91…` | `cbd482ddc2ebfa0c5b86409043de5f3720dc8f94728a5b531f7de6d76d22d4c8` |
| After | `8a162b524d8687d49cd27c25dfc376da577e784f` | `a393b4510d8c73d7…` | `71e2b2c41c4cb84f4b48205cdb78f233f1e23505af2314d334260714c44a69d6` |

OMZ is commit `605a393f1c4734b23c6551370b9d542724e77879`.

## Scope

The measurement covers warm starts with a reusable completion dump. It does not measure the first start after the dump is deleted, the first Tab, or a `.zshrc` with plugins. Completion correctness is covered by `tests/interactive-defaults.py` and the installed completion suite, not by this run.
