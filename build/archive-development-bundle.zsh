#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail
umask 022

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly bundle=${1:-}
readonly output_root=${2:-}
readonly cargo_target_dir=${CARGO_TARGET_DIR:-${repository_root}/target}
readonly manager=${WSH_MANAGER:-${cargo_target_dir}/release/wsh}
readonly source_date_epoch=${SOURCE_DATE_EPOCH:-}

[[ -n $bundle && -d $bundle ]] || {
  print -u2 -- 'usage: archive-development-bundle.zsh BUNDLE OUTPUT_DIRECTORY'
  exit 1
}
[[ -n $output_root ]] || {
  print -u2 -- 'usage: archive-development-bundle.zsh BUNDLE OUTPUT_DIRECTORY'
  exit 1
}
[[ $source_date_epoch == <1-> ]] || {
  print -u2 -- 'error: SOURCE_DATE_EPOCH must be a positive integer'
  exit 1
}
for command in cmp jq mkdir mktemp mv rm sha256sum tar xz; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done
[[ -x $manager ]] || {
  print -u2 -- "error: bundle manager is unavailable: $manager"
  exit 1
}

${manager} bundle verify $bundle >/dev/null
readonly bundle_identity=${bundle:t}
[[ $bundle_identity =~ '^[0-9a-f]{64}$' ]] || {
  print -u2 -- "error: bundle directory is not a manifest digest: $bundle_identity"
  exit 1
}

manifest_status=$(jq -er '.status' ${bundle}/manifest.json)
release_id=$(jq -er '.release_id' ${bundle}/manifest.json)
target=$(jq -er '.target' ${bundle}/manifest.json)
case $manifest_status in
  development)
    archive_name=wsh-development-${target}-${bundle_identity}.tar.xz
    ;;
  release)
    [[ $release_id =~ '^v[0-9]+\.[0-9]+\.[0-9]+$' ]] || {
      print -u2 -- "error: invalid release identity in manifest: $release_id"
      exit 1
    }
    archive_name=wsh-${release_id}-${target}.tar.xz
    ;;
  *)
    print -u2 -- "error: unsupported bundle status in manifest: $manifest_status"
    exit 1
    ;;
esac

mkdir -p -- $output_root
readonly archive_name
readonly destination=${output_root}/${archive_name}
temporary_archive=$(mktemp ${output_root}/.${archive_name}.XXXXXX)
extract_root=$(mktemp -d ${output_root}/.verify.${bundle_identity}.XXXXXX)
trap 'rm -rf -- $temporary_archive $extract_root' EXIT INT TERM

tar \
  --sort=name \
  --format=gnu \
  --mtime=@${source_date_epoch} \
  --owner=0 \
  --group=0 \
  --numeric-owner \
  --mode=u+rwX,go+rX,go-w \
  --directory=${bundle:h} \
  --create \
  --file=- \
  $bundle_identity \
  | xz --threads=1 --check=sha256 --lzma2=preset=9e --stdout >| $temporary_archive

xz --decompress --stdout $temporary_archive | tar --extract --file=- --directory=$extract_root
${manager} bundle verify ${extract_root}/${bundle_identity} >/dev/null

if [[ -e $destination ]]; then
  cmp --silent $temporary_archive $destination || {
    print -u2 -- "error: canonical archive differs from existing output: $destination"
    exit 1
  }
  rm -- $temporary_archive
else
  mv -- $temporary_archive $destination
fi
rm -rf -- $extract_root
trap - EXIT INT TERM

archive_sha256=$(sha256sum $destination)
print -r -- "${archive_sha256%% *}  $destination"
