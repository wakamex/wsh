#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly cargo_target_dir=${CARGO_TARGET_DIR:-${repository_root}/target}
readonly maximum_glibc=${WSH_MINIMUM_GLIBC:-}
readonly archive_output_root=${WSH_ARCHIVE_OUTPUT_ROOT:-}

for command in cargo cp diff find git jq mkdir mktemp od readelf rm sed sort tail tr; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

${script_dir}/verify-rust-toolchain.zsh >/dev/null

built_bundle=$(zsh ${script_dir}/build-development-bundle.zsh)
bundle_identity=${built_bundle:t}
bundle_status=$(jq -er '.status' ${built_bundle}/manifest.json)
test_root=$(mktemp -d /tmp/wsh-floor-bundle.XXXXXX)
trap 'rm -rf -- $test_root' EXIT INT TERM
bundle=${test_root}/relocated-bundle
cp -R --preserve=mode -- $built_bundle $bundle
runtime=${bundle}/bin/wsh-runtime
test_zsh=${bundle}/bin/zsh
manager=${cargo_target_dir}/release/wsh
installer=${cargo_target_dir}/release/wsh-install
theme=${bundle}/share/wsh/themes/minimal.toml

cargo test --locked --workspace
[[ -x $installer ]] || {
  print -u2 -- 'error: release installer was not built'
  exit 1
}
${manager} bundle verify ${bundle} >/dev/null
${bundle}/bin/zsh --version
WSH_BUNDLE_ROOT=${bundle} \
ZDOTDIR=${bundle}/share/wsh/zdotdir \
  ${bundle}/bin/zsh -d -c 'zmodload zsh/datetime'
${runtime} validate-theme ${theme}
state_root=${test_root}/state
${manager} bundle activate ${bundle} --state-root ${state_root} >/dev/null
launched_pid_file=${test_root}/launched.pid
${manager} run --state-root ${state_root} -- -c 'zmodload zsh/datetime; print -r -- $$' > ${launched_pid_file} &
launcher_pid=$!
wait $launcher_pid
[[ $(< ${launched_pid_file}) == $launcher_pid ]] || {
  print -u2 -- 'error: manager did not replace itself with bundled Zsh'
  exit 1
}
bare_input_file=${test_root}/bare.input
bare_pid_file=${test_root}/bare.pid
print -r -- 'zmodload zsh/datetime; print -r -- $$' > ${bare_input_file}
WSH_STATE_ROOT=${state_root} ${manager} < ${bare_input_file} > ${bare_pid_file} &
bare_launcher_pid=$!
wait $bare_launcher_pid
[[ $(< ${bare_pid_file}) == $bare_launcher_pid ]] || {
  print -u2 -- 'error: bare wsh did not replace itself with bundled Zsh'
  exit 1
}

fixture=${test_root}/fixture
mkdir -p -- $fixture
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh floor test'
git -C $fixture config user.email floor-test@wsh.invalid
print -r -- tracked > ${fixture}/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial
cwd_hex=$(print -rn -- $fixture | od -An -tx1 | tr -d ' \n')
coproc ${runtime} serve --theme ${theme}
runtime_pid=$!
exec {runtime_input}>&p
exec {runtime_output}<&p
read -r -t 1 -u $runtime_output ready
[[ $ready == '{"version":1,"type":"ready","theme":'* ]]
print -r -u $runtime_input -- "{\"type\":\"refresh\",\"version\":1,\"id\":1,\"generation\":1,\"cwd_hex\":\"${cwd_hex}\",\"exit_status\":0,\"duration_ms\":null,\"privileged\":false,\"reset_transient\":false}"
read -r -t 3 -u $runtime_output snapshot
print -r -- $snapshot | jq -e '.type == "snapshot" and .snapshot.found == true and .snapshot.branch == "main"' >/dev/null
print -r -u $runtime_input -- '{"type":"shutdown","version":1,"id":2}'
read -r -t 3 -u $runtime_output stopping
[[ $stopping == '{"version":1,"type":"stopping","id":2}' ]]
exec {runtime_input}>&-
exec {runtime_output}<&-
wait $runtime_pid

WSH_TEST_ZSH=${bundle}/bin/zsh \
WSH_TEST_RUNTIME=${runtime} \
WSH_TEST_INTEGRATION=${bundle}/share/wsh/integration.zsh \
WSH_TEST_THEME=${theme} \
WSH_TEST_PROMPT_MARKER='git:main' \
WSH_TEST_BUNDLE_ROOT=${bundle} \
${test_zsh} ${repository_root}/tests/runtime-pty.zsh

${test_zsh} ${repository_root}/tests/zsh-config-coexistence.zsh ${manager} ${bundle} present
${test_zsh} ${repository_root}/tests/history-substring-search.zsh ${manager} ${bundle}
${test_zsh} ${repository_root}/tests/autosuggestions.zsh ${manager} ${bundle}
${test_zsh} ${repository_root}/tests/syntax-highlighting.zsh ${manager} ${bundle}
${test_zsh} ${repository_root}/tests/plugin-doctor.zsh ${manager} ${bundle}
${test_zsh} ${repository_root}/tests/foreground-startup.zsh ${manager} ${bundle} candidate
WSH_EXPECT_NATIVE_TERMINAL_PASS=1 \
  ${test_zsh} ${repository_root}/tests/native-terminal-integration.zsh ${bundle}/bin/zsh /dev/null native ${test_root}/native-terminal.bin >/dev/null

zsh_version=$(${bundle}/bin/zsh -fc 'print -r -- $ZSH_VERSION')
if [[ $zsh_version == 5.9.999.3-test ]]; then
  terminal_policy_zdotdir=${test_root}/terminal-policy-zdotdir
  mkdir -p -- $terminal_policy_zdotdir
  terminal_policy_default=$(HOME=$terminal_policy_zdotdir ZDOTDIR=$terminal_policy_zdotdir WSH_STATE_ROOT=$state_root TERM=dumb \
    ${manager} run --state-root $state_root -- -dic 'typeset -p .term.extensions')
  [[ $terminal_policy_default == *'.term.extensions=( -query )'* ]] || {
    print -u2 -r -- "edge Zsh terminal-query default was not disabled: ${(qqq)terminal_policy_default}"
    exit 1
  }
  print -r -- 'typeset -ga .term.extensions=(-query -color)' > $terminal_policy_zdotdir/.zshenv
  terminal_policy_user=$(HOME=$terminal_policy_zdotdir ZDOTDIR=$terminal_policy_zdotdir WSH_STATE_ROOT=$state_root TERM=dumb \
    ${manager} run --state-root $state_root -- -dic 'typeset -p .term.extensions')
  [[ $terminal_policy_user == *'.term.extensions=( -query -color )'* ]] || {
    print -u2 -r -- "explicit edge Zsh terminal policy was not preserved: ${(qqq)terminal_policy_user}"
    exit 1
  }
fi

needed=$(find ${bundle} -type f -exec readelf -d {} \; 2>/dev/null | sed -n 's/.*Shared library: \[\(.*\)\]/\1/p' | sort -u)
recorded=$(jq -r '.requirements.dynamic_libraries[]' ${bundle}/manifest.json | sort -u)
diff -u <(print -r -- $needed) <(print -r -- $recorded)

if [[ -n $maximum_glibc ]]; then
  actual_glibc=$(find ${bundle} ${manager} ${installer} -type f -exec readelf --version-info {} \; 2>/dev/null | sed -n 's/.*\(GLIBC_[0-9][0-9.]*\).*/\1/p' | sort -Vu | tail -n 1)
  [[ -n $actual_glibc ]] || {
    print -u2 -- 'error: could not determine the newest imported glibc symbol'
    exit 1
  }
  newest=$(print -r -- GLIBC_${maximum_glibc} $actual_glibc | tr ' ' '\n' | sort -Vu | tail -n 1)
  [[ $newest == GLIBC_${maximum_glibc} ]] || {
    print -u2 -- "error: bundle imports $actual_glibc above the GLIBC_${maximum_glibc} floor"
    exit 1
  }
fi

if [[ -n $archive_output_root ]]; then
  SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-} \
    WSH_MANAGER=$manager \
    ${script_dir}/archive-development-bundle.zsh $built_bundle $archive_output_root
fi

print -r -- "PASS: relocated ${bundle_status} bundle ${bundle_identity} on glibc floor; newest imported symbol ${actual_glibc:-not-checked}"
