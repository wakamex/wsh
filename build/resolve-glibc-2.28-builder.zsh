#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly lock=${1:-${script_dir}/glibc-2.28-builder.lock}
readonly package_lock=${2:-${script_dir}/rocky-8.10-packages.lock}
readonly recipe=${3:-${script_dir}/Containerfile.glibc-2.28-builder}

for input in $lock $package_lock $recipe; do
  [[ -f $input ]] || {
    print -u2 -- "error: builder input not found: $input"
    exit 1
  }
done

readonly lines=("${(@f)$(<$lock)}")
(( ${#lines} == 4 )) || {
  print -u2 -- 'error: builder lock must contain exactly four records'
  exit 1
}

readonly image=${lines[1]#image=}
readonly source_revision=${lines[2]#source_revision=}
readonly expected_package_lock_sha256=${lines[3]#package_lock_sha256=}
readonly expected_recipe_sha256=${lines[4]#recipe_sha256=}

[[ ${lines[1]} == image=* && $image =~ '^ghcr\.io/wakamex/wsh-builder-glibc-2\.28@sha256:[0-9a-f]{64}$' ]] || {
  print -u2 -- 'error: invalid glibc 2.28 builder image reference'
  exit 1
}
[[ ${lines[2]} == source_revision=* && $source_revision =~ '^[0-9a-f]{40}$' ]] || {
  print -u2 -- 'error: invalid glibc 2.28 builder source revision'
  exit 1
}
[[ ${lines[3]} == package_lock_sha256=* && $expected_package_lock_sha256 =~ '^[0-9a-f]{64}$' ]] || {
  print -u2 -- 'error: invalid glibc 2.28 package-lock digest'
  exit 1
}
[[ ${lines[4]} == recipe_sha256=* && $expected_recipe_sha256 =~ '^[0-9a-f]{64}$' ]] || {
  print -u2 -- 'error: invalid glibc 2.28 builder-recipe digest'
  exit 1
}

package_lock_record=$(sha256sum -- $package_lock)
readonly actual_package_lock_sha256=${package_lock_record%% *}
recipe_record=$(sha256sum -- $recipe)
readonly actual_recipe_sha256=${recipe_record%% *}

[[ $actual_package_lock_sha256 == $expected_package_lock_sha256 ]] || {
  print -u2 -- 'error: builder image does not match the current Rocky package lock'
  exit 1
}
[[ $actual_recipe_sha256 == $expected_recipe_sha256 ]] || {
  print -u2 -- 'error: builder image does not match the current builder recipe'
  exit 1
}

print -r -- $image
