#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail
umask 022

readonly script_dir=${0:A:h}
readonly template=${script_dir}/bootstrap-install.sh.in
readonly tag=${1:-}
readonly commit=${2:-}
readonly archive=${3:-}
readonly launcher=${4:-}
readonly installer=${5:-}
readonly output=${6:-}
readonly base_url=${7:-https://github.com/wakamex/wsh/releases/download/${tag}}

[[ $tag =~ '^v[0-9]+\.[0-9]+\.[0-9]+$' ]] || {
  print -u2 -- 'error: tag must be canonical vMAJOR.MINOR.PATCH'
  exit 1
}
[[ $commit =~ '^[0-9a-f]{40}$' ]] || {
  print -u2 -- 'error: commit must be a lowercase 40-hex Git identity'
  exit 1
}
[[ -f $archive && ! -L $archive && -f $launcher && ! -L $launcher && -f $installer && ! -L $installer ]] || {
  print -u2 -- 'error: archive, launcher, and installer must be regular files'
  exit 1
}
[[ -n $output && ! -e $output && ! -L $output ]] || {
  print -u2 -- 'error: output must not already exist'
  exit 1
}
[[ $base_url =~ '^(https|file)://[A-Za-z0-9._~:/%+-]+$' && $base_url != */ ]] || {
  print -u2 -- 'error: release base URL must be a simple https or file directory URL without a trailing slash'
  exit 1
}
for command in chmod mkdir sha256sum; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

readonly archive_name=${archive:t}
readonly launcher_name=${launcher:t}
readonly installer_name=${installer:t}
for name in $archive_name $launcher_name $installer_name; do
  [[ $name =~ '^[A-Za-z0-9._-]+$' ]] || {
    print -u2 -- "error: unsafe release asset name: $name"
    exit 1
  }
done
readonly attestation_name=wsh-${tag}-build-provenance.sigstore.json
launcher_digest=$(sha256sum $launcher)
installer_digest=$(sha256sum $installer)
readonly launcher_digest=${launcher_digest%% *}
readonly installer_digest=${installer_digest%% *}

rendered=$(<$template)
rendered=${rendered//@RELEASE_TAG@/$tag}
rendered=${rendered//@SOURCE_COMMIT@/$commit}
rendered=${rendered//@RELEASE_BASE_URL@/$base_url}
rendered=${rendered//@ARCHIVE_NAME@/$archive_name}
rendered=${rendered//@ATTESTATION_NAME@/$attestation_name}
rendered=${rendered//@LAUNCHER_NAME@/$launcher_name}
rendered=${rendered//@LAUNCHER_SHA256@/$launcher_digest}
rendered=${rendered//@INSTALLER_NAME@/$installer_name}
rendered=${rendered//@INSTALLER_SHA256@/$installer_digest}

mkdir -p -- ${output:h}
print -r -- $rendered > $output
chmod 755 $output
print -r -- $output
