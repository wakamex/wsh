#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent

local root=${0:A:h:h}
local evidence=$root/benchmarks/syntax-highlighting-2026-09-03
local temporary=$(mktemp -d /var/tmp/wsh-syntax-highlighting-evidence.XXXXXX)
trap 'command rm -rf -- $temporary' EXIT INT TERM

cd $evidence
print -r -- '4d09b0da404e13acd0caad7bee45a438bd36ddd7792ec245e8a34e7947be7961  startup.tsv
cdaa2ca4ff34ee83ad05fd4904ccda1301f0f3ff2f1449f028ff6125ca089263  edit-baseline.tsv
c53e6fc54eab8ae5d33a01c32554558eaadb2921b74a90cda0ee0cdd6adf7110  edit-candidate.tsv
551972b03334a51a32c331f701ba3fca0472fc43b1a851b1377f25ce3daf6cce  summary.tsv
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  process-trace/edit-window.trace
ebafdc07e6614d28d5138860689c950cb69cf15cded7be9fff42a852e07d9b97  process-trace/executables.tsv
9a94cd27c79a74c3bb38b1796a2bb333cbfa49efd6fd15b8672947e49d37882f  process-trace/metadata.txt
56507719715c8cf45a5031997c6bb4e0109a576e28a36814e86d13b91608bc8f  upstream-tests.log' | sha256sum -c - >/dev/null

print -r -- '2070743a71dbdccd323f1848e8f9f1fd893081c4e779f9f5a3cebcee6b2e467d  third_party/zsh-syntax-highlighting/.revision-hash
97fd9d491486c9c26ce918b0ad429584dddd807f34655f2342872d8175383094  third_party/zsh-syntax-highlighting/.version
d810908db3cb75d30e46f5e55b18c8f483e1bc625b8f7dc5a581f5ad353af82e  third_party/zsh-syntax-highlighting/COPYING.md
156ebe9530eb991dcef54d476967e2ff4338d35dabaaff9e5462673a287cc63b  third_party/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
b3ac4a66edf133b8f029332e787b7d36e2e1d7cabec0d271f7e5fe6724490dd3  third_party/zsh-syntax-highlighting/highlighters/brackets/brackets-highlighter.zsh
bd6ef3aae900fee57ff132360b3dd9d68df5aab150a33e32259fd5adbe8efd49  third_party/zsh-syntax-highlighting/highlighters/cursor/cursor-highlighter.zsh
1a12c094770bc00276395dc71a398a63fd768c433453d35f4e47e5d315dfacf0  third_party/zsh-syntax-highlighting/highlighters/line/line-highlighter.zsh
d63bf09783100d426d0eb068872ea42b87d9609c49deb0d063daaa173223e7fd  third_party/zsh-syntax-highlighting/highlighters/main/main-highlighter.zsh
c2d5b50db13936421672b5ce16c0d7ec4f1abfeded34ea3a23bb39d2499b953b  third_party/zsh-syntax-highlighting/highlighters/pattern/pattern-highlighter.zsh
f567458da4fb89cae8ea220b8febea11ed67ab6f6c8f5e0d6723ea7285e932e7  third_party/zsh-syntax-highlighting/highlighters/regexp/regexp-highlighter.zsh
6d14a315685176dcc317842064b4a1e061b1e87b0623d4bee688ee780de831e7  integration/syntax-highlighting.zsh
88bff44041ed35327c3dc4099dedc45ca9c8aa966ac45cff7d4f6fb4351e07dd  integration/zdotdir.zshrc' | (cd $root && sha256sum -c - >/dev/null)

$root/benchmarks/summarize-syntax-highlighting.zsh startup.tsv edit-baseline.tsv edit-candidate.tsv $temporary/summary.tsv >/dev/null
diff -u summary.tsv $temporary/summary.tsv

awk -F '\t' '
  NR == 1 { next }
  { samples[$2 SUBSEP $5]++ }
  END {
    expected["baseline" SUBSEP "clean"] = 40
    expected["baseline" SUBSEP "external"] = 40
    expected["baseline" SUBSEP "external-ready"] = 40
    expected["candidate" SUBSEP "disabled"] = 40
    expected["candidate" SUBSEP "clean"] = 40
    expected["candidate" SUBSEP "external"] = 40
    expected["candidate" SUBSEP "external-ready"] = 40
    for (variant in expected) {
      if (samples[variant] != expected[variant]) exit 1
    }
    if (length(samples) != length(expected)) exit 1
  }
' startup.tsv

awk -F '\t' '
  FNR == 1 { next }
  { samples[$2 SUBSEP $5 SUBSEP $6]++ }
  END {
    expected["baseline" SUBSEP "external-ready" SUBSEP "short"] = 100
    expected["baseline" SUBSEP "external-ready" SUBSEP "long"] = 100
    expected["candidate" SUBSEP "clean" SUBSEP "short"] = 100
    expected["candidate" SUBSEP "clean" SUBSEP "long"] = 100
    expected["candidate" SUBSEP "external" SUBSEP "short"] = 100
    expected["candidate" SUBSEP "external" SUBSEP "long"] = 100
    for (variant in expected) {
      if (samples[variant] != expected[variant]) exit 1
    }
    if (length(samples) != length(expected)) exit 1
  }
' edit-baseline.tsv edit-candidate.tsv

awk -F '\t' '
  NR == 1 { next }
  $1 == "first-editable" && $2 == "baseline" && $3 == "clean" { baseline_clean = $7 }
  $1 == "first-editable" && $2 == "baseline" && $3 == "external-ready" { baseline_external_ready = $7 }
  $1 == "first-editable" && $2 == "candidate" && $3 == "disabled" { candidate_disabled = $7 }
  $1 == "first-editable" && $2 == "candidate" && $3 == "clean" { candidate_clean = $7 }
  $1 == "first-editable" && $2 == "candidate" && $3 == "external" { candidate_external = $7 }
  $1 == "first-editable" && $2 == "candidate" && $3 == "external-ready" { candidate_external_ready = $7 }
  $1 == "redraw" && $2 == "baseline" { redraw_baseline[$4] = $7 }
  $1 == "redraw" && $2 == "candidate" && $3 == "clean" { redraw_clean[$4] = $7 }
  $1 == "redraw" && $2 == "candidate" && $3 == "external" { redraw_external[$4] = $7 }
  END {
    if (candidate_clean - baseline_external_ready > 1.0) exit 1
    if (candidate_external - baseline_external_ready > 3.0) exit 1
    if (candidate_external_ready - baseline_external_ready > 3.0) exit 1
    if (candidate_disabled - baseline_clean > 0.25) exit 1
    for (workload in redraw_baseline) {
      if (redraw_clean[workload] > redraw_baseline[workload] * 1.20) exit 1
      if (redraw_external[workload] > redraw_baseline[workload] * 1.20) exit 1
    }
  }
' summary.tsv

[[ $(sed -n 's/^owner=//p' process-trace/metadata.txt) == 'external-exact|1' ]]
[[ $(sed -n 's/^edit_window_process_creations=//p' process-trace/metadata.txt) == 0 ]]
[[ $(sed -n 's/^edit_window_execve=//p' process-trace/metadata.txt) == 0 ]]
awk -F '\t' 'NR > 1 && ($2 == "sha256sum" || $2 == "cmp") { exit 1 }' process-trace/executables.tsv
awk '/ (execve|fork|vfork|clone|clone3)\(/ { exit 1 }' process-trace/edit-window.trace

[[ $(grep -c '^variant=' upstream-tests.log) == 2 ]]
[[ $(grep -c '^variant=upstream$' upstream-tests.log) == 1 ]]
[[ $(grep -c '^variant=bundled-runtime$' upstream-tests.log) == 1 ]]
[[ $(grep -c '^ZSH_PATCHLEVEL=zsh-5.9.2-0-gddee3e7$' upstream-tests.log) == 2 ]]
for suite in brackets main pattern regexp; do
  [[ $(grep -c "^Running test ${suite}$" upstream-tests.log) == 2 ]]
done

print -r -- 'PASS: syntax-highlighting digests, upstream suite, sample counts, startup, redraw, and process gates'
