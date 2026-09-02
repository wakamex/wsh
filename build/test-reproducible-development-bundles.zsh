#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail
umask 022

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly output_root=${1:-}
readonly requested_revision=${2:-HEAD}

[[ -n $output_root ]] || {
  print -u2 -- 'usage: test-reproducible-development-bundles.zsh OUTPUT_DIRECTORY [REVISION]'
  exit 1
}
for command in cmp cp cut find git mkdir mktemp rm sha256sum; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done
[[ -z $(git -C $repository_root status --porcelain --untracked-files=all) ]] || {
  print -u2 -- 'error: reproducibility test requires a clean source worktree'
  exit 1
}
readonly revision=$(git -C $repository_root rev-parse ${requested_revision}^{commit})
[[ ! -e $output_root && ! -L $output_root ]] || {
  print -u2 -- "error: output already exists: $output_root"
  exit 1
}
mkdir -p -- $output_root

readonly scratch_root=$(mktemp -d /var/tmp/wsh-reproducibility.XXXXXX)
typeset -a registered_worktrees=()
integer completed=0

cleanup() {
  if (( completed )); then
    for worker_source in $registered_worktrees; do
      git -C $repository_root worktree remove --force $worker_source 2>/dev/null || true
    done
    rm -rf -- $scratch_root
  else
    print -u2 -- "preserved failed reproducibility workers: $scratch_root"
  fi
}
trap cleanup EXIT INT TERM

for worker_name in a b; do
  worker_source=${scratch_root}/worker-${worker_name}
  git -C $repository_root worktree add --detach $worker_source $revision >/dev/null
  registered_worktrees+=($worker_source)
  worker_log=${output_root}/worker-${worker_name}.log
  print -r -- "worker=$worker_name revision=$revision source=$worker_source" >| $worker_log
  (
    cd $worker_source
    ./build/build-glibc-2.28-development-bundle.zsh
  ) >> $worker_log 2>&1

  worker_archives=(${worker_source}/build/portable/glibc-2.28/archives/*.tar.xz(N))
  worker_bundles=(${worker_source}/build/portable/glibc-2.28/bundles/*(N/))
  (( ${#worker_archives} == 1 && ${#worker_bundles} == 1 )) || {
    print -u2 -- "error: worker $worker_name did not produce exactly one archive and bundle"
    exit 1
  }
  cp -- $worker_archives[1] ${output_root}/worker-${worker_name}.tar.xz
  cp -- ${worker_bundles[1]}/manifest.json ${output_root}/worker-${worker_name}.manifest.json
done

readonly archive_a=${output_root}/worker-a.tar.xz
readonly archive_b=${output_root}/worker-b.tar.xz
readonly manifest_a=${output_root}/worker-a.manifest.json
readonly manifest_b=${output_root}/worker-b.manifest.json
archive_a_sha256=$(sha256sum $archive_a)
archive_b_sha256=$(sha256sum $archive_b)
manifest_a_sha256=$(sha256sum $manifest_a)
manifest_b_sha256=$(sha256sum $manifest_b)
archive_a_sha256=${archive_a_sha256%% *}
archive_b_sha256=${archive_b_sha256%% *}
manifest_a_sha256=${manifest_a_sha256%% *}
manifest_b_sha256=${manifest_b_sha256%% *}

{
  print -r -- 'format_version=1'
  print -r -- "source_revision=$revision"
  print -r -- "archive_a_sha256=$archive_a_sha256"
  print -r -- "archive_b_sha256=$archive_b_sha256"
  print -r -- "manifest_a_sha256=$manifest_a_sha256"
  print -r -- "manifest_b_sha256=$manifest_b_sha256"
  print -r -- "package_lock_sha256=$(sha256sum ${repository_root}/build/rocky-8.10-packages.lock | cut -d ' ' -f 1)"
  print -r -- "rust_toolchain_lock_sha256=$(sha256sum ${repository_root}/build/rust-toolchain.lock | cut -d ' ' -f 1)"
} >| ${output_root}/result.txt

cmp --silent $manifest_a $manifest_b || {
  print -u2 -- 'error: isolated bundle manifests differ'
  exit 1
}
cmp --silent $archive_a $archive_b || {
  print -u2 -- 'error: isolated canonical archives differ'
  exit 1
}

print -r -- 'byte_identical=1' >> ${output_root}/result.txt
completed=1
print -r -- "PASS: two isolated archives are byte-identical at $archive_a_sha256"
