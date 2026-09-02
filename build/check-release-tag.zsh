#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly tag=${1:-}

[[ $tag =~ '^v[0-9]+\.[0-9]+\.[0-9]+$' ]] || {
  print -u2 -- 'usage: check-release-tag.zsh vMAJOR.MINOR.PATCH'
  exit 1
}
for command in cargo git jq; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done
[[ -z $(git -C $repository_root status --porcelain --untracked-files=all) ]] || {
  print -u2 -- 'error: release tag validation requires a clean worktree'
  exit 1
}
[[ $(git -C $repository_root cat-file -t refs/tags/${tag} 2>/dev/null) == tag ]] || {
  print -u2 -- "error: release tag must exist locally and be annotated: $tag"
  exit 1
}
readonly head_revision=$(git -C $repository_root rev-parse HEAD)
readonly tag_revision=$(git -C $repository_root rev-parse ${tag}^{commit})
[[ $tag_revision == $head_revision ]] || {
  print -u2 -- "error: release tag $tag resolves to $tag_revision instead of HEAD $head_revision"
  exit 1
}

typeset -a workspace_versions
workspace_versions=(${(f)$(cargo metadata --locked --no-deps --format-version 1 --manifest-path ${repository_root}/Cargo.toml | jq -r '[.packages[].version] | unique[]')})
(( ${#workspace_versions} == 1 )) || {
  print -u2 -- 'error: release packages do not share exactly one version'
  exit 1
}
[[ v${workspace_versions[1]} == $tag ]] || {
  print -u2 -- "error: release tag $tag does not match workspace version ${workspace_versions[1]}"
  exit 1
}

print -r -- "$tag $head_revision"
