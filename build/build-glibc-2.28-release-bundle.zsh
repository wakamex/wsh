#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly tag=${1:-}

release_identity=$(${script_dir}/check-release-tag.zsh $tag)
readonly source_revision=${release_identity##* }

WSH_BUNDLE_STATUS=release \
WSH_RELEASE_ID=$tag \
WSH_SOURCE_REVISION=$source_revision \
  ${script_dir}/build-glibc-2.28-development-bundle.zsh
