#!/usr/bin/env zsh
# Render Formula/wsh.rb for a published release and, with --push, publish it to the tap.
# Usage: packaging/homebrew/sync-tap.zsh vX.Y.Z [--push]
# Run from a checkout of the release tag after its GitHub Release exists.
emulate -L zsh
setopt errexit nounset pipefail
(( $# == 1 || $# == 2 )) && [[ $1 == v<->.<->.<-> && ${2:-} == (|--push) ]] || {
  print -u2 -- 'usage: sync-tap.zsh vX.Y.Z [--push]'; exit 2
}
readonly tag=$1 push=${2:-} root=${0:A:h:h:h}
readonly repo=${WSH_REPO:-wakamex/wsh} tap=${HOMEBREW_TAP_REPO:-wakamex/homebrew-tap}
readonly gh=${GH_BIN:-${commands[gh]:-/home/linuxbrew/.linuxbrew/bin/gh}}
[[ $(git -C $root describe --exact-match --tags) == $tag ]] || {
  print -u2 -- "error: the checkout is not at $tag"; exit 1
}
readonly work=$(mktemp -d)
trap 'rm -rf -- $work' EXIT
# The formula may only name an asset of the published Release, with its recorded digest.
$gh release download $tag --repo $repo --pattern SHA256SUMS --dir $work
readonly asset=wsh-$tag-source.tar.gz
readonly sha256=$(awk -v f=$asset '$2 == f {print $1}' $work/SHA256SUMS)
[[ $sha256 =~ '^[0-9a-f]{64}$' ]] || {
  print -u2 -- "error: $asset is not in the $tag SHA256SUMS"; exit 1
}
python3 $root/packaging/homebrew/render-formula.py \
  https://github.com/$repo/releases/download/$tag/$asset $sha256 $(git -C $root rev-parse $tag^{commit}) $work/wsh.rb >/dev/null
print -r -- "Rendered Formula/wsh.rb for $tag (source SHA-256 $sha256)"
[[ $push == --push ]] || { cat $work/wsh.rb; exit 0; }
$gh repo clone $tap $work/tap -- --quiet
mkdir -p $work/tap/Formula
cp $work/wsh.rb $work/tap/Formula/wsh.rb
git -C $work/tap add Formula/wsh.rb
if git -C $work/tap diff --cached --quiet; then
  print -r -- "The tap already has wsh ${tag#v}"; exit 0
fi
git -C $work/tap commit --quiet -m "wsh ${tag#v}"
git -C $work/tap push --quiet origin HEAD
print -r -- "Published wsh ${tag#v} to $tap"
