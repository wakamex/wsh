# Confirmed Zsh bugs for potential upstreaming

This document records local upstream candidates and their submission status. Record the affected source revision, minimal reproducer, expected and observed behavior, proposed fix and verification before considering submission.

## Neutral highlight attributes discard ownership metadata

Affected source: `zsh-users/zsh` commit `cad0d67c76e2be7371cf3526b79ea2581810d35a`. Confirmed using real ZLE on the native development installation before the local fix.

`output_highlight()` serializes an empty attribute mask as `none`, but `match_highlight()` does not consume that token. `set_region_highlight()` therefore stops before following `memo=` or `layer=` fields. A neutral region loses its ownership tag. The syntax-highlighting plugin removes only regions carrying its memo, so these entries survive cleanup, accumulate across redraws and move when the editor inserts text.

Minimal widget reproducer:

```zsh
_probe_highlight_memo() {
  region_highlight=('0 1 none memo=probe')
  typeset -p region_highlight
}
zle -N _probe_highlight_memo
bindkey '^T' _probe_highlight_memo
```

Press Ctrl-T in a real ZLE session. Expected: `region_highlight` retains `memo=probe`. Observed: it becomes `0 1 none`. `fg=green memo=probe` retains the memo. `none,layer=4 memo=probe` loses both layer and memo. The automated reproducer is [native/test-highlight-roundtrip.py](native/test-highlight-roundtrip.py); it records first assignment and subsequent round trips without a fake parameter implementation.

The local patch [cad0d67c-highlight-none.patch](build/zsh-patches/cad0d67c-highlight-none.patch) consumes a delimited `none` token without changing the attribute mask, allowing subsequent attributes and metadata to be parsed. The normal and ASan/UBSan real-ZLE regressions pass all five cases. Host upstream tests, nine installed contracts, all 287 highlighter fixtures, repeated composed redraws and canonical glibc 2.28 qualification pass. The [fix report and retained evidence](benchmarks/zsh-highlight-none-2026-09-10/report.md) identify exact builds and test results.

Upstream submission should include a regression in the upstream real-ZLE highlighting tests, explain the serializer/parser mismatch, and check neutral style combinations and malformed token boundaries. No submission has been made.

## OSC 133 identifier and initial OSC 7 reporting

The pinned post-5.9 terminal integration wrote a generated OSC 133 identifier at an incorrect fixed byte offset, corrupting the `aid=z` field name. Its initial OSC 7 report also depended on an optional terminal query, so disabling an unanswered query removed the initial directory report and could leave a foreground application's directory active in the terminal.

The retained [terminal integration report](benchmarks/native-terminal-integration-2026-09-04/report.md) contains reproducers, authoritative terminal-parser checks and validation. The local patch is [cad0d67c-terminal-integration.patch](build/zsh-patches/cad0d67c-terminal-integration.patch). These are confirmed local fixes; this document does not establish their submission or upstream acceptance status.

## Compiled-function alignment padding contains uninitialized bytes

The pinned compiled-function writer rounded program data to whole words and wrote the rounded size from a heap allocation, including up to three uninitialized bytes. Independent builds could produce different compiled-function bytes and include stale heap data.

The retained [reproducibility report](benchmarks/zcompile-reproducibility-2026-09-04/report.md) records the reproducer and passing zero-padding/reproducibility checks. The local patch is [cad0d67c-zcompile-padding.patch](build/zsh-patches/cad0d67c-zcompile-padding.patch). This is a confirmed local fix; this document does not establish its submission or upstream acceptance status.
