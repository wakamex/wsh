#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly repository_root=${0:A:h:h}
readonly fixture_commit=a5bf996c1f7403731c81b6c105ceedfcc4a93159
readonly fixture_sha256=e21ef23b7b97f16af6638cc6f261b304359be894a016e68d1a6c889d131c0f30
readonly fixture_url=https://raw.githubusercontent.com/combinatrix-ai/attestation-verify/${fixture_commit}/tests/fixtures/github-cli/tarball-user-slsa-provenance.json
readonly output=${1:-}
readonly samples=${2:-100}

[[ -n $output && $samples == <1-> ]] || {
  print -u2 -- 'usage: benchmark-verified-install.zsh OUTPUT.tsv [SAMPLES]'
  exit 1
}
for command in cargo curl mkdir mktemp rm sha256sum; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

mkdir -p -- ${output:h}
fixture=$(mktemp /tmp/wsh-provenance-benchmark.XXXXXX)
trap 'rm -f -- $fixture' EXIT INT TERM
curl --fail --location --retry 3 --output $fixture $fixture_url
print -r -- "${fixture_sha256}  ${fixture}" | sha256sum --check --status

cd $repository_root
cargo build --locked --release -p wsh-install --example benchmark_provenance
target/release/examples/benchmark_provenance $fixture $samples >| $output

print -r -- "PASS: wrote ${samples} offline provenance-verification samples to $output"
