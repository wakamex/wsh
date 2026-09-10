#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
umask 022
readonly root=${0:A:h:h}
readonly image=$(python3 $root/build/prepare-native-builder.py)
readonly sdk_identity=$(podman image inspect --format '{{index .Config.Labels "org.wsh.inputs"}}' $image)
readonly epoch=$(git -C $root show -s --format=%ct HEAD)
revision=$(git -C $root rev-parse HEAD)
[[ -z $(git -C $root status --porcelain --untracked-files=all) ]] || revision+=+dirty
podman run --rm --init --userns=keep-id --network=host \
  --volume $root:/workspace:Z --workdir /workspace \
  --env LANG=C --env LC_ALL=C --env TZ=UTC \
  --env SOURCE_DATE_EPOCH=$epoch --env WSH_SOURCE_REVISION=$revision \
  --env WSH_BUILDER_BASE_IMAGE=native-sdk-sha256:$sdk_identity --env WSH_MINIMUM_GLIBC=2.28 \
  --env WSH_BUILD_JOBS=2 --env WSH_KEEP_FAILED_BUILD=1 \
  --env WSH_BUNDLE_STATUS=${WSH_BUNDLE_STATUS:-development} \
  $image zsh /workspace/build/test-native-installation.zsh
