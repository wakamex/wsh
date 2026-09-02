#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail
umask 022

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly tag=${1:-}
readonly worker=${2:-}
readonly output=${3:-}
readonly portable_root=${repository_root}/build/portable/glibc-2.28

[[ $tag =~ '^v[0-9]+\.[0-9]+\.[0-9]+$' && $worker == [ab] && -n $output ]] || {
  print -u2 -- 'usage: collect-release-build.zsh vMAJOR.MINOR.PATCH a|b OUTPUT_DIRECTORY'
  exit 1
}
for command in cp jq mkdir sha256sum; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done
[[ ! -e $output && ! -L $output ]] || {
  print -u2 -- "error: release build output already exists: $output"
  exit 1
}

typeset -a archives bundles
archives=(${portable_root}/archives/*.tar.xz(N))
bundles=(${portable_root}/bundles/*(N/))
(( ${#archives} == 1 && ${#bundles} == 1 )) || {
  print -u2 -- 'error: canonical build did not produce exactly one archive and bundle'
  exit 1
}
readonly archive=${archives[1]}
readonly manifest=${bundles[1]}/manifest.json
[[ $(jq -er '.status' $manifest) == release ]] || {
  print -u2 -- 'error: canonical output is not a release bundle'
  exit 1
}
[[ $(jq -er '.release_id' $manifest) == $tag ]] || {
  print -u2 -- 'error: canonical output release identity does not match the tag'
  exit 1
}

mkdir -p -- $output
readonly archive_name=${archive:t}
readonly manifest_name=${archive_name%.tar.xz}.manifest.json
cp -- $archive ${output}/${archive_name}
cp -- $manifest ${output}/${manifest_name}
archive_digest=$(sha256sum ${output}/${archive_name})
manifest_digest=$(sha256sum ${output}/${manifest_name})
archive_digest=${archive_digest%% *}
manifest_digest=${manifest_digest%% *}

jq -n \
  --arg worker "$worker" \
  --arg repository "${GITHUB_REPOSITORY:-local}" \
  --arg workflow_ref "${GITHUB_WORKFLOW_REF:-local}" \
  --arg workflow_sha "${GITHUB_WORKFLOW_SHA:-local}" \
  --arg run_id "${GITHUB_RUN_ID:-local}" \
  --arg run_attempt "${GITHUB_RUN_ATTEMPT:-local}" \
  --arg runner_image "${ImageOS:-local}" \
  --arg runner_os "${RUNNER_OS:-Linux}" \
  --arg runner_arch "${RUNNER_ARCH:-X64}" \
  --arg archive "$archive_name" \
  --arg archive_sha256 "$archive_digest" \
  --arg manifest "$manifest_name" \
  --arg manifest_sha256 "$manifest_digest" \
  --slurpfile bundle "$manifest" \
  '{
    format_version:1,
    worker:$worker,
    repository:$repository,
    workflow:{ref:$workflow_ref,sha:$workflow_sha,run_id:$run_id,run_attempt:$run_attempt},
    runner:{image:$runner_image,os:$runner_os,arch:$runner_arch},
    source_revision:$bundle[0].rust.source_revision,
    release_id:$bundle[0].release_id,
    target:$bundle[0].target,
    builder:$bundle[0].builder,
    rust:$bundle[0].rust,
    zsh:$bundle[0].zsh,
    tests:{canonical_floor_suite:"pass"},
    outputs:{archive:{name:$archive,sha256:$archive_sha256},manifest:{name:$manifest,sha256:$manifest_sha256}}
  }' > ${output}/build-record-${worker}.json

print -r -- "${output}/${archive_name}"
