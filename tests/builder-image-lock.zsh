#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly resolver=${repository_root}/build/resolve-glibc-2.28-builder.zsh
readonly expected_image=ghcr.io/wakamex/wsh-builder-glibc-2.28@sha256:74dda0facfec11e403a2cfd17cd6b08cdc4e13f28a9f161c21b1a1b30ac3b1fb
readonly fixture_root=$(mktemp -d)
trap 'rm -rf -- $fixture_root' EXIT

[[ $($resolver) == $expected_image ]]

cp -- ${repository_root}/build/rocky-8.10-packages.lock ${fixture_root}/packages.lock
cp -- ${repository_root}/build/Containerfile.glibc-2.28-builder ${fixture_root}/Containerfile
cp -- ${repository_root}/build/glibc-2.28-builder.lock ${fixture_root}/builder.lock
print -r -- changed >> ${fixture_root}/packages.lock
if $resolver ${fixture_root}/builder.lock ${fixture_root}/packages.lock ${fixture_root}/Containerfile >/dev/null 2>&1; then
  print -u2 -- 'error: changed package lock was accepted'
  exit 1
fi

cp -- ${repository_root}/build/rocky-8.10-packages.lock ${fixture_root}/packages.lock
print -r -- changed >> ${fixture_root}/Containerfile
if $resolver ${fixture_root}/builder.lock ${fixture_root}/packages.lock ${fixture_root}/Containerfile >/dev/null 2>&1; then
  print -u2 -- 'error: changed builder recipe was accepted'
  exit 1
fi

sed 's#^image=.*#image=ghcr.io/wakamex/wsh-builder-glibc-2.28:mutable#' \
  ${repository_root}/build/glibc-2.28-builder.lock > ${fixture_root}/builder.lock
cp -- ${repository_root}/build/Containerfile.glibc-2.28-builder ${fixture_root}/Containerfile
if $resolver ${fixture_root}/builder.lock ${fixture_root}/packages.lock ${fixture_root}/Containerfile >/dev/null 2>&1; then
  print -u2 -- 'error: mutable builder reference was accepted'
  exit 1
fi

print -r -- 'builder image lock tests passed'
