#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly repository_root=${0:A:h:h}
readonly fixture_commit=a5bf996c1f7403731c81b6c105ceedfcc4a93159
readonly fixture_sha256=e21ef23b7b97f16af6638cc6f261b304359be894a016e68d1a6c889d131c0f30
readonly fixture_url=https://raw.githubusercontent.com/combinatrix-ai/attestation-verify/${fixture_commit}/tests/fixtures/github-cli/tarball-user-slsa-provenance.json
readonly artifact_sha256=83d5c2ccad5498f58bf6368acb1ab32588cf43ab3a4b1c301bf36328b1c8bd60
readonly artifact_url=https://github.com/cli/cli/releases/download/v2.96.0/gh_2.96.0_linux_amd64.tar.gz
readonly source_commit=b300f2ec7ec9dc9addc39b2ad88c54097ded7ca0

for command in cargo curl gh mktemp rm sha256sum; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

fixture=$(mktemp --suffix=.json /tmp/wsh-external-attestation.XXXXXX)
artifact=$(mktemp --suffix=.tar.gz /tmp/wsh-external-artifact.XXXXXX)
trap 'rm -f -- $fixture $artifact' EXIT INT TERM
curl --fail --location --retry 3 --output $fixture $fixture_url
print -r -- "${fixture_sha256}  ${fixture}" | sha256sum --check --status
curl --fail --location --retry 3 --output $artifact $artifact_url
print -r -- "${artifact_sha256}  ${artifact}" | sha256sum --check --status

gh attestation verify $artifact \
  --bundle $fixture \
  --repo cli/cli \
  --signer-workflow cli/cli/.github/workflows/deployment.yml \
  --signer-digest $source_commit \
  --source-ref refs/heads/trunk \
  --source-digest $source_commit \
  --deny-self-hosted-runners

WSH_EXTERNAL_ATTESTATION=$fixture \
  cargo test --locked -p wsh-install --test external_attestation -- --ignored --exact verifies_real_github_actions_provenance_and_rejects_substitution

print -r -- 'PASS: real external GitHub Actions provenance verified and substitutions rejected'
