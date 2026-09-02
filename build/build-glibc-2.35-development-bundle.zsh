#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly image=wsh-glibc-2.35-builder:development
readonly portable_root=${repository_root}/build/portable/glibc-2.35
readonly rustup_root=${RUSTUP_HOME:-$HOME/.rustup}
readonly cargo_home=${CARGO_HOME:-$HOME/.cargo}

for command in podman; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done
[[ -d $rustup_root && -d $cargo_home ]] || {
  print -u2 -- 'error: local Rust toolchain is unavailable'
  exit 1
}

mkdir -p -- $portable_root
podman build --pull=never --tag $image --file $script_dir/Containerfile.glibc-2.35 $repository_root
podman run --rm --userns=keep-id --network=host \
  --volume ${repository_root}:/workspace:Z \
  --volume ${rustup_root}:/rustup:ro,Z \
  --volume ${cargo_home}:/cargo:ro,Z \
  --env RUSTUP_HOME=/rustup \
  --env CARGO_HOME=/cargo \
  --env PATH=/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
  --env CARGO_NET_OFFLINE=true \
  --env CARGO_TARGET_DIR=/workspace/build/portable/glibc-2.35/target \
  --env WSH_ZSH_OUTPUT_ROOT=/workspace/build/portable/glibc-2.35/zsh \
  --env WSH_ZSH_ROOT=/workspace/build/portable/glibc-2.35/zsh/zsh-5.9.2 \
  --env WSH_BUNDLE_OUTPUT_ROOT=/workspace/build/portable/glibc-2.35/bundles \
  --env WSH_KEEP_FAILED_BUILD=1 \
  --env WSH_MINIMUM_GLIBC=2.35 \
  --workdir /workspace \
  $image \
  zsh /workspace/build/test-development-bundle.zsh
