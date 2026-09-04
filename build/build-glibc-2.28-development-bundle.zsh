#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail
umask 022

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly portable_root=${repository_root}/build/portable/glibc-2.28
readonly rustup_root=${RUSTUP_HOME:-$HOME/.rustup}
readonly bundle_status=${WSH_BUNDLE_STATUS:-development}
readonly release_id=${WSH_RELEASE_ID:-}
readonly zsh_source_lock=${WSH_ZSH_SOURCE_LOCK:-${script_dir}/zsh-sources/zsh-cad0d67c.json}
readonly image=$(${script_dir}/resolve-glibc-2.28-builder.zsh)

for command in git podman sed sha256sum; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

[[ $zsh_source_lock == ${repository_root}/* ]] || {
  print -u2 -- "error: Zsh source lock must be inside the repository: ${zsh_source_lock}"
  exit 1
}
readonly container_zsh_source_lock=/workspace/${zsh_source_lock#${repository_root}/}

readonly rust_toolchain_name=$(sed -n 's/^toolchain=//p' ${script_dir}/rust-toolchain.lock)
readonly rust_toolchain_root=${rustup_root}/toolchains/${rust_toolchain_name}
readonly rust_toolchain_identity=$(
  WSH_RUST_TOOLCHAIN_ROOT=$rust_toolchain_root ${script_dir}/verify-rust-toolchain.zsh
)
readonly rust_toolchain_sha256=${rust_toolchain_identity##* }
package_lock_record=$(sha256sum ${script_dir}/rocky-8.10-packages.lock)
readonly package_lock_sha256=${package_lock_record%% *}
readonly source_date_epoch=$(git -C $repository_root show -s --format=%ct HEAD)
source_revision=$(git -C $repository_root rev-parse HEAD)
if [[ -n $(git -C $repository_root status --short --untracked-files=all) ]]; then
  source_revision="${source_revision}+dirty"
fi
readonly source_revision

mkdir -p -- $portable_root
podman image exists $image || podman pull $image
podman run --rm --userns=keep-id --network=host \
  --volume ${repository_root}:/workspace:Z \
  --volume ${rust_toolchain_root}:/toolchain:ro,Z \
  --env WSH_RUST_TOOLCHAIN_ROOT=/toolchain \
  --env CARGO_HOME=/workspace/build/portable/glibc-2.28/cargo-home \
  --env CARGO_BUILD_JOBS=1 \
  --env CARGO_NET_OFFLINE=${WSH_CARGO_NET_OFFLINE:-false} \
  --env PATH=/toolchain/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  --env CARGO_TARGET_DIR=/workspace/build/portable/glibc-2.28/target \
  --env LANG=C \
  --env LC_ALL=C \
  --env SOURCE_DATE_EPOCH=$source_date_epoch \
  --env TZ=UTC \
  --env WSH_ARCHIVE_OUTPUT_ROOT=/workspace/build/portable/glibc-2.28/archives \
  --env WSH_BUILDER_BASE_IMAGE=$image \
  --env WSH_BUILDER_PACKAGE_LOCK_SHA256=$package_lock_sha256 \
  --env WSH_ZSH_OUTPUT_ROOT=/workspace/build/portable/glibc-2.28/zsh \
  --env WSH_ZSH_SOURCE_LOCK=$container_zsh_source_lock \
  --env WSH_BUNDLE_OUTPUT_ROOT=/workspace/build/portable/glibc-2.28/bundles \
  --env WSH_KEEP_FAILED_BUILD=1 \
  --env WSH_MINIMUM_GLIBC=2.28 \
  --env WSH_BUILD_JOBS=1 \
  --env WSH_BUNDLE_STATUS=$bundle_status \
  --env WSH_RELEASE_ID=$release_id \
  --env WSH_RUST_TOOLCHAIN_SHA256=$rust_toolchain_sha256 \
  --env WSH_SOURCE_REVISION=$source_revision \
  --workdir /workspace \
  $image \
  zsh /workspace/build/test-development-bundle.zsh
