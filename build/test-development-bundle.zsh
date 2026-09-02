#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly cargo_target_dir=${CARGO_TARGET_DIR:-${repository_root}/target}
readonly maximum_glibc=${WSH_MINIMUM_GLIBC:-}

for command in cargo cp diff find git jq mkdir mktemp od readelf rm sed sort tail tr; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

built_bundle=$(zsh ${script_dir}/build-development-bundle.zsh)
bundle_identity=${built_bundle:t}
test_root=$(mktemp -d /tmp/wsh-floor-bundle.XXXXXX)
trap 'rm -rf -- $test_root' EXIT INT TERM
bundle=${test_root}/relocated-bundle
cp -R -- $built_bundle $bundle
runtime=${bundle}/bin/wsh-runtime
manager=${cargo_target_dir}/release/wsh
theme=${bundle}/share/wsh/themes/minimal.toml

cargo test --locked --workspace
${manager} bundle verify ${bundle} >/dev/null
${bundle}/bin/zsh --version
${runtime} validate-theme ${theme}
${manager} run --bundle ${bundle} -- -c 'zmodload zsh/datetime'

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
${repository_root}/tests/runtime-pty.zsh

needed=$(find ${bundle} -type f -exec readelf -d {} \; 2>/dev/null | sed -n 's/.*Shared library: \[\(.*\)\]/\1/p' | sort -u)
recorded=$(jq -r '.requirements.dynamic_libraries[]' ${bundle}/manifest.json | sort -u)
diff -u <(print -r -- $needed) <(print -r -- $recorded)

if [[ -n $maximum_glibc ]]; then
  actual_glibc=$(find ${bundle} -type f -exec readelf --version-info {} \; 2>/dev/null | sed -n 's/.*\(GLIBC_[0-9][0-9.]*\).*/\1/p' | sort -Vu | tail -n 1)
  [[ -n $actual_glibc ]] || {
    print -u2 -- 'error: could not determine the maximum required glibc symbol'
    exit 1
  }
  newest=$(print -r -- GLIBC_${maximum_glibc} $actual_glibc | tr ' ' '\n' | sort -Vu | tail -n 1)
  [[ $newest == GLIBC_${maximum_glibc} ]] || {
    print -u2 -- "error: bundle requires $actual_glibc above the GLIBC_${maximum_glibc} floor"
    exit 1
  }
fi

print -r -- "PASS: relocated development bundle ${bundle_identity} on glibc floor; maximum required symbol ${actual_glibc:-not-checked}"
