# Syntax highlighting should reuse the established ZLE hook path without duplicate ownership

The accepted autosuggestions bundle `1cf00759912729597db3a760fa5d4aafa3afbb2bfb17ff5267ab3ab18978bfa6` has no syntax-highlighting layer unless user configuration loads executable code. This experiment pins `zsh-users/zsh-syntax-highlighting` commit `2fc57d63067c18b1100ecdbf684fa5baf49459d1`, tests its runtime files with the upstream suite, and compares direct `.zshrc` loading with a precompiled trusted bundle component.

## The smallest counterfactual keeps the upstream redraw-hook design

Zsh 5.9.2 lets the plugin use `add-zle-hook-widget` for `zle-line-pre-redraw` and `zle-line-finish`, avoiding its legacy path that wraps every widget. Wsh retains that implementation and its six shipped highlighters without adding a highlight broker, native module, or Rust parsing interface. The default remains the upstream `main` highlighter, while the documented style map and highlighter list remain configurable before Wsh loads.

The baseline found that an ordinary external copy sourced through Wsh's nested user-startup path sees ZLE as inactive. It defines its functions and parses its highlighters but installs neither the modern redraw hooks nor legacy widget wrappers, so highlighting silently does nothing. Loading `zsh/zle` before the same source is the working direct-upstream control. The smallest candidate defers clean bundled loading until the first `precmd`, when ZLE is active. For an exact core and exact active highlighter set, it installs the upstream redraw hooks around the already loaded functions instead of parsing the same files twice. Modified active files, custom active highlighters, incomplete installations, and unknown implementations remain external. A later doctor result can perform the non-startup comparison of the complete installation before recommending removal of a redundant declaration.

## Correctness gates include upstream semantics and actual ZLE composition

The candidate passes only when:

- The pinned upstream test suite passes with the bundled Zsh against both the original checkout and the runtime files copied from the candidate bundle.
- Actual ZLE input produces the expected command, unknown-token, quoted-argument, and path highlight regions, and clearing or accepting a line removes stale regions.
- Substring history search, asynchronous autosuggestions, and syntax highlighting retain one owner each and preserve both the visible suggestion suffix and syntax regions.
- A pre-existing custom redraw hook runs once, documented styles and enabled highlighters remain configurable, and explicit disablement loads no bundled hooks.
- An exact core and active highlighter set is recognized and activated without a second source pass. A modified active runtime file and a custom active highlighter remain the sole external owner.

## Performance gates cover startup and redraw work

Startup uses 5 warmups followed by 20 forward-order and 20 reverse-order launches pinned to CPU 0. The clean bundled default may add at most 1 ms p90 over the working direct-upstream control that loads ZLE before the plugin. Both recognized exact paths may add at most 3 ms p90 over that working control. The ordinary pre-change external path is retained as the reproduced no-hook correctness failure rather than used as a performance control for working highlighting. The disabled adapter may add at most 0.25 ms p90 over the accepted autosuggestions bundle.

The recognized-path budget was initially 1 ms. Comparing every shipped runtime file added about 3.5 ms, and limiting the hot-path comparison to the exact core plus active highlighters reduced the adapter to 1.83 ms under `zprof` and about 2 ms in paired first-editable measurements. Exact content verification and automatic repair of the reproduced no-hook state are required for safe takeover. A native module, helper process, or recognition cache is disproportionate for a transitional declaration that doctor can remove, so the fixed compatibility budget is 3 ms. The clean default and disabled paths retain their original gates.

A long-lived PTY records at least 100 short valid-command redraws and 100 1,000-byte buffer redraws after warmup. Candidate p90 may be no more than 20 percent slower than direct upstream for either workload. The isolated syntax path disables autosuggestions so each edit executes no program and creates no worker. A composed correctness fixture retains autosuggestions' separately accepted one-worker bound.

The pinned runtime and in-process exact-file recognition are the planned path. A gate failure leaves syntax highlighting external before adding a new parser, widget broker, resident process, or native Zsh module.
