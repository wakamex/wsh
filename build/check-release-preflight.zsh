#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly tag=${1:-}
readonly repository=${GITHUB_REPOSITORY:-wakamex/wsh}

[[ $tag =~ '^v[0-9]+\.[0-9]+\.[0-9]+$' ]] || {
  print -u2 -- 'usage: check-release-preflight.zsh vMAJOR.MINOR.PATCH'
  exit 2
}
[[ $repository == wakamex/wsh ]] || {
  print -u2 -- "error: release preflight is fixed to wakamex/wsh, not $repository"
  exit 1
}
for command in cargo gh git jq; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

[[ $(git -C $repository_root branch --show-current) == main ]] || {
  print -u2 -- 'error: release preflight requires the main branch'
  exit 1
}
[[ -z $(git -C $repository_root status --porcelain --untracked-files=all) ]] || {
  print -u2 -- 'error: release preflight requires a clean worktree'
  exit 1
}

git -C $repository_root fetch --quiet origin main --tags
readonly head_revision=$(git -C $repository_root rev-parse HEAD)
remote_main_record=$(git -C $repository_root ls-remote --heads origin refs/heads/main)
readonly remote_main_revision=${remote_main_record%%[[:space:]]*}
[[ $remote_main_revision == $head_revision ]] || {
  print -u2 -- "error: remote main is $remote_main_revision instead of $head_revision"
  exit 1
}

[[ -z $(git -C $repository_root show-ref --verify --hash refs/tags/${tag} 2>/dev/null) ]] || {
  print -u2 -- "error: local release tag already exists: $tag"
  exit 1
}
[[ -z $(git -C $repository_root ls-remote --tags origin "refs/tags/${tag}" "refs/tags/${tag}^{}") ]] || {
  print -u2 -- "error: remote release tag already exists: $tag"
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

typeset -a release_tags
release_tags=(${(f)$(gh api --method GET --paginate repos/${repository}/releases -f per_page=100 --jq '.[].tag_name')})
(( ${release_tags[(Ie)$tag]} == 0 )) || {
  print -u2 -- "error: GitHub Release already exists: $tag"
  exit 1
}

workflow_runs=$(gh api --method GET repos/${repository}/actions/workflows/release-eligibility.yml/runs \
  -f head_sha=$head_revision \
  -f branch=main \
  -f event=push \
  -f status=success \
  -f per_page=100)
print -r -- $workflow_runs | jq -e --arg revision $head_revision '
  [.workflow_runs[] | select(
    .head_sha == $revision and
    .head_branch == "main" and
    .event == "push" and
    .status == "completed" and
    .conclusion == "success"
  )] | length >= 1
' >/dev/null || {
  print -u2 -- "error: no successful main-push validation run exists for $head_revision"
  exit 1
}

print -r -- "$tag $head_revision release-ready"
