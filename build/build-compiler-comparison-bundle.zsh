#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail
umask 022

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly image=wsh-glibc-2.28-builder:development
readonly rustup_root=${RUSTUP_HOME:-$HOME/.rustup}

usage() {
  print -r -- 'usage: build-compiler-comparison-bundle.zsh gcc-8.5.0|gcc-16.2.0|clang-23.1.0'
}

(( $# == 1 )) || {
  usage >&2
  exit 2
}

readonly variant=$1
local compiler_mount=()
local compiler_environment=()
case $variant in
  gcc-8.5.0)
    compiler_environment=(--env CC=/usr/bin/gcc)
    ;;
  gcc-16.2.0)
    readonly compiler_root=${WSH_GCC_16_ROOT:-${repository_root}/build/portable/toolchains/gcc-16.2.0}
    [[ -x ${compiler_root}/bin/gcc ]] || {
      print -u2 -- "error: GCC 16.2.0 toolchain not found: ${compiler_root}"
      exit 1
    }
    compiler_mount=(--volume ${compiler_root}:/gcc:ro,Z)
    compiler_environment=(--env CC=/gcc/bin/gcc)
    ;;
  clang-23.1.0)
    readonly compiler_root=${WSH_CLANG_23_ROOT:-${repository_root}/build/portable/toolchains/clang-23.1.0}
    [[ -x ${compiler_root}/bin/clang ]] || {
      print -u2 -- "error: Clang 23.1.0 toolchain not found: ${compiler_root}"
      exit 1
    }
    compiler_mount=(--volume ${compiler_root}:/clang:ro,Z)
    compiler_environment=(--env CC=/clang/bin/clang)
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

for command in git podman sed sha256sum; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done

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
readonly portable_root=${repository_root}/build/portable/compiler-comparison/${variant}

mkdir -p -- $portable_root
podman build --pull=never --tag $image --file $script_dir/Containerfile.glibc-2.28 $repository_root
podman run --rm --userns=keep-id --network=host \
  --volume ${repository_root}:/workspace:Z \
  --volume ${portable_root}:/comparison:Z \
  --volume ${rust_toolchain_root}:/toolchain:ro,Z \
  $compiler_mount \
  $compiler_environment \
  --env WSH_RUST_TOOLCHAIN_ROOT=/toolchain \
  --env CARGO_HOME=/workspace/build/portable/compiler-comparison/shared-cargo-home \
  --env CARGO_BUILD_JOBS=1 \
  --env CARGO_NET_OFFLINE=${WSH_CARGO_NET_OFFLINE:-false} \
  --env PATH=/toolchain/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  --env CARGO_TARGET_DIR=/workspace/build/portable/compiler-comparison/shared-target \
  --env LANG=C \
  --env LC_ALL=C \
  --env SOURCE_DATE_EPOCH=$source_date_epoch \
  --env TZ=UTC \
  --env WSH_ARCHIVE_OUTPUT_ROOT=/comparison/archives \
  --env WSH_BUILDER_BASE_IMAGE=quay.io/rockylinux/rockylinux@sha256:f5529992e67440c1a4ae7788244d4381c6909159a88eacd95b7523ae47ced82e \
  --env WSH_BUILDER_PACKAGE_LOCK_SHA256=$package_lock_sha256 \
  --env WSH_ZSH_OUTPUT_ROOT=/comparison/zsh \
  --env WSH_ZSH_ROOT=/comparison/zsh/zsh-5.9.2 \
  --env WSH_BUNDLE_OUTPUT_ROOT=/comparison/bundles \
  --env WSH_KEEP_FAILED_BUILD=1 \
  --env WSH_MINIMUM_GLIBC=2.28 \
  --env WSH_BUILD_JOBS=1 \
  --env WSH_RUST_TOOLCHAIN_SHA256=$rust_toolchain_sha256 \
  --env WSH_SOURCE_REVISION=$source_revision \
  --workdir /workspace \
  $image \
  zsh /workspace/build/test-development-bundle.zsh
