#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly repository_root=${0:A:h:h}
readonly manager=${repository_root}/target/debug/wsh
readonly release_tag=v0.1.1
readonly release_commit=e62e19fe1cf8b10d28b703e2670b6478e540f38d
readonly bootstrap_url=https://github.com/wakamex/wsh/releases/download/${release_tag}/wsh-${release_tag}-install.sh
readonly real_curl=$commands[curl]

for command in cargo curl jq mkdir mktemp rm sed; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

test_root=$(mktemp -d /tmp/wsh-update-cli.XXXXXX)
trap 'rm -rf -- $test_root' EXIT INT TERM
readonly test_home=${test_root}/home
readonly bin_root=${test_root}/bin
readonly libexec_root=${test_root}/libexec
readonly state_root=${test_root}/state
readonly temporary_root=${test_root}/tmp
readonly fake_bin=${test_root}/fake-bin
readonly curl_record=${test_root}/curl-record
readonly bootstrap_record=${test_root}/bootstrap-record
mkdir -p -- $test_home $bin_root $libexec_root $state_root $temporary_root $fake_bin

readonly release_bootstrap=${test_root}/release-install.sh
$real_curl --disable --proto '=https' --proto-redir '=https' --tlsv1.2 --fail --location --retry 3 --silent --show-error --output $release_bootstrap $bootstrap_url
HOME=$test_home WSH_BIN_DIR=$bin_root WSH_LIBEXEC_DIR=$libexec_root WSH_STATE_ROOT=$state_root sh $release_bootstrap >/dev/null
readonly installed_bundle=$($bin_root/wsh bundle current --state-root $state_root)
[[ $(jq -r '.status + " " + .release_id + " " + .rust.source_revision' $installed_bundle/manifest.json) == "release $release_tag $release_commit" ]]

cargo build --locked -p wsh >/dev/null

cat > ${fake_bin}/curl <<'EOF'
#!/bin/sh
set -eu

if [ "$#" -eq 18 ] \
  && [ "$1" = --disable ] \
  && [ "$2" = --proto ] \
  && [ "$3" = =https ] \
  && [ "$4" = --proto-redir ] \
  && [ "$5" = =https ] \
  && [ "$6" = --tlsv1.2 ] \
  && [ "$7" = --fail ] \
  && [ "$8" = --location ] \
  && [ "$9" = --retry ] \
  && [ "${10}" = 3 ] \
  && [ "${11}" = --silent ] \
  && [ "${12}" = --show-error ] \
  && [ "${13}" = --output ] \
  && [ "${14}" = /dev/null ] \
  && [ "${15}" = --write-out ] \
  && [ "${16}" = '%{url_effective}' ] \
  && [ "${17}" = -- ] \
  && [ "${18}" = https://github.com/wakamex/wsh/releases/latest ]; then
  printf '%s\n' latest >> "$WSH_CURL_RECORD"
  printf '%s' "${WSH_FAKE_LATEST_URL:-https://github.com/wakamex/wsh/releases/tag/$WSH_FAKE_LATEST_TAG}"
  exit 0
fi

if [ "$#" -eq 16 ] \
  && [ "$1" = --disable ] \
  && [ "$2" = --proto ] \
  && [ "$3" = =https ] \
  && [ "$4" = --proto-redir ] \
  && [ "$5" = =https ] \
  && [ "$6" = --tlsv1.2 ] \
  && [ "$7" = --fail ] \
  && [ "$8" = --location ] \
  && [ "$9" = --retry ] \
  && [ "${10}" = 3 ] \
  && [ "${11}" = --silent ] \
  && [ "${12}" = --show-error ] \
  && [ "${13}" = --output ] \
  && [ "${15}" = -- ] \
  && [ "${16}" = "https://github.com/wakamex/wsh/releases/download/$WSH_FAKE_LATEST_TAG/wsh-$WSH_FAKE_LATEST_TAG-install.sh" ]; then
  printf '%s\n' download >> "$WSH_CURL_RECORD"
  if [ "${WSH_FAKE_DOWNLOAD_EXIT:-0}" -ne 0 ]; then
    printf '%s\n' 'controlled download failure' >&2
    exit "$WSH_FAKE_DOWNLOAD_EXIT"
  fi
  printf '%s\n' \
    '#!/bin/sh' \
    'printf "%s\t%s\n" "$WSH_FAKE_LATEST_TAG" "$WSH_STATE_ROOT" > "$WSH_BOOTSTRAP_RECORD"' \
    'exit "${WSH_FAKE_BOOTSTRAP_EXIT:-0}"' > "${14}"
  exit 0
fi

printf '%s\n' 'unexpected curl contract' >&2
exit 97
EOF
chmod 755 ${fake_bin}/curl

run_fake() {
  env \
    HOME=$test_home \
    PATH=${fake_bin}:$PATH \
    TMPDIR=$temporary_root \
    WSH_BOOTSTRAP_RECORD=$bootstrap_record \
    WSH_CURL_RECORD=$curl_record \
    WSH_FAKE_BOOTSTRAP_EXIT=${WSH_FAKE_BOOTSTRAP_EXIT:-0} \
    WSH_FAKE_DOWNLOAD_EXIT=${WSH_FAKE_DOWNLOAD_EXIT:-0} \
    WSH_FAKE_LATEST_TAG=v0.1.4 \
    WSH_FAKE_LATEST_URL=${WSH_FAKE_LATEST_URL:-} \
    $manager update "$@" --state-root $state_root
}

assert_temporary_root_empty() {
  local -a entries
  entries=(${temporary_root}/*(N))
  (( ${#entries} == 0 ))
}

check_output=$(run_fake --check)
[[ $check_output == 'wsh v0.1.4 is available; current release is v0.1.1.' ]]
[[ $(<$curl_record) == latest && ! -e $bootstrap_record ]]

rm -f -- $curl_record $bootstrap_record
same_output=$(run_fake --to v0.1.1)
[[ $same_output == 'wsh v0.1.1 is up to date.' && ! -e $curl_record && ! -e $bootstrap_record ]]

! run_fake --to v0.1.0 >${test_root}/downgrade.out 2>${test_root}/downgrade.err
grep -F 'refusing to update from v0.1.1 to older release v0.1.0' ${test_root}/downgrade.err >/dev/null
[[ ! -e $curl_record && ! -e $bootstrap_record ]]

! run_fake --to v01.1.4 >${test_root}/invalid.out 2>${test_root}/invalid.err
grep -F 'release tag must be canonical vMAJOR.MINOR.PATCH' ${test_root}/invalid.err >/dev/null
[[ ! -e $curl_record && ! -e $bootstrap_record ]]

! WSH_FAKE_LATEST_URL=https://example.com/wakamex/wsh/releases/tag/v0.1.4 run_fake --check >${test_root}/redirect.out 2>${test_root}/redirect.err
grep -F 'GitHub redirected the latest release to an unexpected URL' ${test_root}/redirect.err >/dev/null
[[ $(<$curl_record) == latest && ! -e $bootstrap_record ]]

rm -f -- $curl_record $bootstrap_record
run_fake --to v0.1.4 >/dev/null
[[ $(<$curl_record) == download ]]
[[ $(<$bootstrap_record) == $'v0.1.4\t'${state_root} ]]
assert_temporary_root_empty

rm -f -- $curl_record $bootstrap_record
run_fake >/dev/null
[[ $(<$curl_record) == $'latest\ndownload' ]]
[[ $(<$bootstrap_record) == $'v0.1.4\t'${state_root} ]]
assert_temporary_root_empty

rm -f -- $curl_record $bootstrap_record
! WSH_FAKE_DOWNLOAD_EXIT=22 run_fake --to v0.1.4 >${test_root}/download.out 2>${test_root}/download.err
grep -F 'could not download the v0.1.4 release bootstrap: controlled download failure' ${test_root}/download.err >/dev/null
[[ $(<$curl_record) == download && ! -e $bootstrap_record ]]
assert_temporary_root_empty

rm -f -- $curl_record $bootstrap_record
! WSH_FAKE_BOOTSTRAP_EXIT=7 run_fake --to v0.1.4 >${test_root}/bootstrap.out 2>${test_root}/bootstrap.err
grep -F 'v0.1.4 release bootstrap failed with exit status 7' ${test_root}/bootstrap.err >/dev/null
[[ $(<$curl_record) == download ]]
[[ $(<$bootstrap_record) == $'v0.1.4\t'${state_root} ]]
assert_temporary_root_empty

live_output=$(HOME=$test_home PATH=$PATH TMPDIR=$temporary_root $manager update --check --state-root $state_root)
[[ $live_output == 'wsh v'*' is available; current release is v0.1.1.' ]]
assert_temporary_root_empty

print -r -- 'PASS: explicit update check, exact selection, latest selection, no-op, downgrade rejection, cleanup, failure handling, and live GitHub discovery'
