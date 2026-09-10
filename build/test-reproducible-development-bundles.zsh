#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
readonly root=${0:A:h:h}
readonly output=${1:?usage: test-reproducible-development-bundles.zsh NEW_OUTPUT [REVISION]}
readonly revision=$(git -C $root rev-parse ${2:-HEAD}^{commit})
[[ -z $(git -C $root status --porcelain --untracked-files=all) && ! -e $output ]] || {
  print -u2 -- 'error: a clean worktree and new output directory are required'
  exit 1
}
mkdir -p $output
readonly destination=${output:A}
for worker in a b; do
  source=$destination/source-$worker
  git -C $root worktree add --detach $source $revision
  (cd $source && ./build/build-glibc-2.28-development-bundle.zsh) > $destination/build-$worker.log 2>&1
  mkdir $destination/$worker
  manifests=($source/build/portable/glibc-2.28/bundles/*/manifest.json(N))
  packages=($source/build/portable/glibc-2.28/rpm/RPMS/**/*.rpm(N))
  (( $#manifests == 1 && $#packages == 1 ))
  cp $manifests[1] $destination/$worker/manifest.json
  cp $packages[1] $destination/$worker/package.rpm
  git -C $root worktree remove --force $source
 done
cmp $destination/a/manifest.json $destination/b/manifest.json
cmp $destination/a/package.rpm $destination/b/package.rpm
sha256sum $destination/{a,b}/{manifest.json,package.rpm} > $destination/SHA256SUMS
print -r -- 'PASS: independent native installations and RPMs are byte-identical'
