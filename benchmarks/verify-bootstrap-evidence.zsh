#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly repository_root=${0:A:h:h}
readonly evidence=${repository_root}/benchmarks/bootstrap-install-2026-09-02
readonly metadata=${evidence}/metadata.txt
readonly samples=${evidence}/samples.tsv

metadata_value() {
  local key=$1
  sed -n "s/^${key}=//p" $metadata
}

verify_hash() {
  local key=$1
  local input_file=$2
  local actual=$(sha256sum $input_file)
  [[ ${actual%% *} == $(metadata_value $key) ]] || {
    print -u2 -- "error: retained bootstrap evidence hash mismatch: $key"
    exit 1
  }
}

verify_hash samples_sha256 $samples
verify_hash bootstrap_template_sha256 ${repository_root}/build/bootstrap-install.sh.in
verify_hash renderer_sha256 ${repository_root}/build/render-bootstrap.zsh
verify_hash test_sha256 ${repository_root}/tests/bootstrap-install.zsh
verify_hash publish_workflow_sha256 ${repository_root}/.github/workflows/publish.yml

readonly summary=$(
  awk -F '\t' 'NR > 1 { print $2 }' $samples \
    | sort -n \
    | awk 'BEGIN { n=0 } { a[++n]=$1 } END { p90=int((n*90+99)/100); if (n%2) median=a[(n+1)/2]; else median=(a[n/2]+a[n/2+1])/2; printf "%d\t%.3f\t%.3f\t%.3f", n, median/1000000, a[p90]/1000000, a[n]/1000000 }'
)
[[ $summary == $'30\t60.298\t61.642\t63.932' ]] || {
  print -u2 -- "error: retained bootstrap summary changed: $summary"
  exit 1
}

print -r -- 'PASS: retained bootstrap inputs, implementation digests, and summary agree'
