#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly lock_file=${script_dir}/rust-toolchain.lock
typeset -A locked
local lock_line lock_key lock_value

for command in find sha256sum sort; do
  (( $+commands[$command] )) || {
    print -u2 -- "error: required command not found: $command"
    exit 1
  }
done
[[ -f $lock_file ]] || {
  print -u2 -- "error: Rust toolchain lock is unavailable: $lock_file"
  exit 1
}

while IFS= read -r lock_line; do
  [[ $lock_line == *=* ]] || {
    print -u2 -- "error: malformed Rust toolchain lock line: $lock_line"
    exit 1
  }
  lock_key=${lock_line%%=*}
  lock_value=${lock_line#*=}
  locked[$lock_key]=$lock_value
done < $lock_file

for lock_key in toolchain rustc_version cargo_version tree_sha256; do
  [[ -n ${locked[$lock_key]:-} ]] || {
    print -u2 -- "error: Rust toolchain lock omits $lock_key"
    exit 1
  }
done

readonly toolchain_root=${WSH_RUST_TOOLCHAIN_ROOT:-${RUSTUP_HOME:-$HOME/.rustup}/toolchains/${locked[toolchain]}}
[[ -x ${toolchain_root}/bin/rustc && -x ${toolchain_root}/bin/cargo ]] || {
  print -u2 -- "error: locked Rust toolchain is unavailable at $toolchain_root"
  exit 1
}
[[ $(${toolchain_root}/bin/rustc --version) == ${locked[rustc_version]} ]] || {
  print -u2 -- 'error: rustc version does not match build/rust-toolchain.lock'
  exit 1
}
[[ $(${toolchain_root}/bin/cargo --version) == ${locked[cargo_version]} ]] || {
  print -u2 -- 'error: cargo version does not match build/rust-toolchain.lock'
  exit 1
}

actual_tree_sha256=$(
  find -L $toolchain_root -type f -print0 \
    | sort -z \
    | while IFS= read -r -d '' toolchain_file; do
        relative_file=${toolchain_file#${toolchain_root}/}
        file_sha256=$(sha256sum $toolchain_file)
        print -rn -- "${relative_file}\0${file_sha256%% *}\0"
      done \
    | sha256sum
)
actual_tree_sha256=${actual_tree_sha256%% *}
[[ $actual_tree_sha256 == ${locked[tree_sha256]} ]] || {
  print -u2 -- "error: Rust toolchain tree digest is $actual_tree_sha256; expected ${locked[tree_sha256]}"
  exit 1
}

print -r -- "${locked[toolchain]} ${locked[tree_sha256]}"
