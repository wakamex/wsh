#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly tag=${1:-}
readonly repository=${GITHUB_REPOSITORY:-wakamex/wsh}

for command in gh git jq; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done
[[ $repository == wakamex/wsh ]] || {
  print -u2 -- "error: release eligibility is fixed to wakamex/wsh, not $repository"
  exit 1
}
release_identity=$(${script_dir}/check-release-tag.zsh $tag)
readonly source_revision=${release_identity##* }

git -C $repository_root fetch --quiet origin main
git -C $repository_root merge-base --is-ancestor $source_revision refs/remotes/origin/main || {
  print -u2 -- "error: release commit is not on origin/main: $source_revision"
  exit 1
}

workflow_runs=$(gh api --method GET repos/${repository}/actions/workflows/release-eligibility.yml/runs \
  -f head_sha=$source_revision \
  -f branch=main \
  -f event=push \
  -f status=success \
  -f per_page=100)
print -r -- $workflow_runs | jq -e --arg revision $source_revision '
  [.workflow_runs[] | select(
    .head_sha == $revision and
    .head_branch == "main" and
    .event == "push" and
    .status == "completed" and
    .conclusion == "success"
  )] | length >= 1
' >/dev/null || {
  print -u2 -- "error: no successful main-push validation run exists for $source_revision"
  exit 1
}

print -r -- "$tag $source_revision release-eligible"
