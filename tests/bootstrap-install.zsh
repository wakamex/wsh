#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly repository_root=${0:A:h:h}
readonly tag=v0.1.0
readonly commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
readonly benchmark_output=${1:-}
readonly benchmark_samples=${2:-30}
[[ -z $benchmark_output || ( $benchmark_samples == <1-> && ! -e $benchmark_output && ! -L $benchmark_output ) ]] || {
  print -u2 -- 'usage: bootstrap-install.zsh [NEW-BENCHMARK-OUTPUT.tsv [SAMPLES]]'
  exit 1
}
test_root=$(mktemp -d /tmp/wsh-bootstrap-test.XXXXXX)
trap 'rm -rf -- $test_root' EXIT INT TERM
readonly assets=${test_root}/assets
readonly archive_name=wsh-${tag}-x86_64-unknown-linux-gnu-${commit}.tar.xz
readonly attestation_name=wsh-${tag}-build-provenance.sigstore.json
readonly launcher_name=wsh-launcher-${tag}-x86_64-unknown-linux-gnu
readonly installer_name=wsh-install-${tag}-x86_64-unknown-linux-gnu
mkdir -p -- $assets
print -rn -- 'archive fixture' > ${assets}/${archive_name}
print -rn -- 'attestation fixture' > ${assets}/${attestation_name}
cat > ${assets}/${launcher_name} <<'EOF'
#!/bin/sh
exit 0
EOF
cat > ${assets}/${installer_name} <<'EOF'
#!/bin/sh
set -eu
[ "$#" -eq 9 ]
[ "$1" = install ]
[ "$2" = --archive ]
[ "${3##*/}" = 'wsh-v0.1.0-x86_64-unknown-linux-gnu-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.tar.xz' ]
[ "$4" = --attestation ]
[ "${5##*/}" = 'wsh-v0.1.0-build-provenance.sigstore.json' ]
[ "$6" = --tag ]
[ "$7" = v0.1.0 ]
[ "$8" = --commit ]
[ "$9" = aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa ]
echo executed >> "$WSH_TEST_RECORD"
EOF
chmod 755 ${assets}/${launcher_name} ${assets}/${installer_name}

render() {
  output=$1
  ${repository_root}/build/render-bootstrap.zsh \
    $tag \
    $commit \
    ${assets}/${archive_name} \
    ${assets}/${launcher_name} \
    ${assets}/${installer_name} \
    $output \
    file://${assets} >/dev/null
}

run_bootstrap() {
  root=$1
  shift
  mkdir -p -- $root/home
  HOME=$root/home \
    WSH_BIN_DIR=$root/bin \
    WSH_LIBEXEC_DIR=$root/libexec \
    WSH_TEST_RECORD=$root/executions \
    PATH=$PATH \
    "$@"
}

readonly first=${test_root}/install-a.sh
readonly second=${test_root}/install-b.sh
render $first
render $second
cmp --silent $first $second

readonly collector_root=${test_root}/collector
readonly collector_portable=${collector_root}/build/portable/glibc-2.28
readonly collector_bundle=${collector_portable}/bundles/${commit}
mkdir -p -- ${collector_root}/build ${collector_portable}/archives ${collector_bundle} ${collector_portable}/target/release
cp -- ${repository_root}/build/collect-release-build.zsh ${repository_root}/build/render-bootstrap.zsh ${repository_root}/build/bootstrap-install.sh.in ${collector_root}/build/
cp -- ${assets}/${archive_name} ${collector_portable}/archives/${archive_name}
cp -- ${assets}/${launcher_name} ${collector_portable}/target/release/wsh
cp -- ${assets}/${installer_name} ${collector_portable}/target/release/wsh-install
cat > ${collector_bundle}/manifest.json <<EOF
{"status":"release","release_id":"$tag","target":"x86_64-unknown-linux-gnu","builder":{},"rust":{"source_revision":"$commit"},"zsh":{}}
EOF
readonly collected=${test_root}/collected
${collector_root}/build/collect-release-build.zsh $tag a $collected >/dev/null
[[ -x ${collected}/wsh-${tag}-install.sh ]]
[[ $(jq -r '.outputs.bootstrap.name' ${collected}/build-record-a.json) == wsh-${tag}-install.sh ]]
readonly recorded_bootstrap_digest=$(jq -r '.outputs.bootstrap.sha256' ${collected}/build-record-a.json)
actual_bootstrap_digest=$(sha256sum ${collected}/wsh-${tag}-install.sh)
[[ ${actual_bootstrap_digest%% *} == $recorded_bootstrap_digest ]]

readonly success=${test_root}/success
run_bootstrap $success $first >/dev/null
cmp --silent ${assets}/${launcher_name} ${success}/bin/wsh
cmp --silent ${assets}/${installer_name} ${success}/libexec/wsh-install
[[ $(wc -l < ${success}/executions) == 1 ]]
run_bootstrap $success $first >/dev/null
[[ $(wc -l < ${success}/executions) == 2 ]]

cp -- ${assets}/${installer_name} ${assets}/${installer_name}.original
print -r -- 'tampered' >> ${assets}/${installer_name}
readonly bad_installer=${test_root}/bad-installer
! run_bootstrap $bad_installer $first >/dev/null 2>${bad_installer}.error
grep -F 'SHA-256 mismatch' ${bad_installer}.error >/dev/null
[[ ! -e ${bad_installer}/executions && ! -e ${bad_installer}/bin/wsh && ! -e ${bad_installer}/libexec/wsh-install ]]
mv -- ${assets}/${installer_name}.original ${assets}/${installer_name}

cp -- ${assets}/${launcher_name} ${assets}/${launcher_name}.original
print -r -- 'tampered' >> ${assets}/${launcher_name}
readonly bad_launcher=${test_root}/bad-launcher
! run_bootstrap $bad_launcher $first >/dev/null 2>${bad_launcher}.error
grep -F 'SHA-256 mismatch' ${bad_launcher}.error >/dev/null
[[ ! -e ${bad_launcher}/executions && ! -e ${bad_launcher}/bin/wsh && ! -e ${bad_launcher}/libexec/wsh-install ]]
mv -- ${assets}/${launcher_name}.original ${assets}/${launcher_name}

mv -- ${assets}/${archive_name} ${assets}/${archive_name}.missing
readonly missing=${test_root}/missing
! run_bootstrap $missing $first >/dev/null 2>${missing}.error
grep -F 'curl:' ${missing}.error >/dev/null
[[ ! -e ${missing}/executions && ! -e ${missing}/bin/wsh && ! -e ${missing}/libexec/wsh-install ]]
mv -- ${assets}/${archive_name}.missing ${assets}/${archive_name}

readonly conflict=${test_root}/conflict
mkdir -p -- ${conflict}/bin
print -rn -- 'existing' > ${conflict}/bin/wsh
readonly conflict_digest=$(sha256sum ${conflict}/bin/wsh)
! run_bootstrap $conflict $first >/dev/null 2>${conflict}.error
grep -F 'SHA-256 mismatch' ${conflict}.error >/dev/null
[[ $(sha256sum ${conflict}/bin/wsh) == $conflict_digest && ! -e ${conflict}/executions && ! -e ${conflict}/libexec/wsh-install ]]

readonly linked=${test_root}/linked
mkdir -p -- ${linked}/bin
ln -s /bin/false ${linked}/bin/wsh
! run_bootstrap $linked $first >/dev/null 2>${linked}.error
grep -F 'existing tool is not a regular file' ${linked}.error >/dev/null
[[ -L ${linked}/bin/wsh && ! -e ${linked}/executions && ! -e ${linked}/libexec/wsh-install ]]

readonly unsupported=${test_root}/unsupported
mkdir -p -- ${unsupported}/fake-bin
cat > ${unsupported}/fake-bin/uname <<'EOF'
#!/bin/sh
echo Darwin
EOF
chmod 755 ${unsupported}/fake-bin/uname
! PATH=${unsupported}/fake-bin:$PATH run_bootstrap $unsupported $first >/dev/null 2>${unsupported}.error
grep -F 'this release supports Linux only' ${unsupported}.error >/dev/null
[[ ! -e ${unsupported}/executions && ! -e ${unsupported}/bin/wsh && ! -e ${unsupported}/libexec/wsh-install ]]

readonly old_glibc=${test_root}/old-glibc
mkdir -p -- ${old_glibc}/fake-bin
cat > ${old_glibc}/fake-bin/getconf <<'EOF'
#!/bin/sh
echo 'glibc 2.27'
EOF
chmod 755 ${old_glibc}/fake-bin/getconf
! PATH=${old_glibc}/fake-bin:$PATH run_bootstrap $old_glibc $first >/dev/null 2>${old_glibc}.error
grep -F 'this release requires glibc 2.28 or newer, found 2.27' ${old_glibc}.error >/dev/null
[[ ! -e ${old_glibc}/executions && ! -e ${old_glibc}/bin/wsh && ! -e ${old_glibc}/libexec/wsh-install ]]

if [[ -n $benchmark_output ]]; then
  mkdir -p -- ${benchmark_output:h}
  print -r -- $'sample\telapsed_ns' > $benchmark_output
  integer sample
  for (( sample = 1; sample <= benchmark_samples; sample++ )); do
    sample_root=${test_root}/benchmark-${sample}
    started=$(date +%s%N)
    run_bootstrap $sample_root $first >/dev/null
    finished=$(date +%s%N)
    print -r -- "${sample}"$'\t'"$(( finished - started ))" >> $benchmark_output
  done
fi

print -r -- 'PASS: release bootstrap is deterministic, rerunnable, and rejects substitution and unsafe destinations'
