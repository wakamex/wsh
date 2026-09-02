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

for lock_key in toolchain rustc_version cargo_version components required_components_sha256; do
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

typeset -a required_components
required_components=(${(s:,:)locked[components]})
(( ${#required_components} > 0 )) || {
  print -u2 -- 'error: Rust toolchain lock has no required components'
  exit 1
}

actual_components_sha256=$(
  for component in $required_components; do
    [[ $component =~ '^[a-z0-9._-]+$' ]] || {
      print -u2 -- "error: invalid locked Rust component: $component"
      exit 1
    }
    component_manifest=lib/rustlib/manifest-${component}
    [[ -f ${toolchain_root}/${component_manifest} ]] || {
      print -u2 -- "error: locked Rust component is unavailable: $component"
      exit 1
    }
    component_manifest_sha256=$(sha256sum ${toolchain_root}/${component_manifest})
    print -rn -- "${component_manifest}\0${component_manifest_sha256%% *}\0"
    while IFS= read -r component_entry; do
      [[ $component_entry == file:* ]] || continue
      relative_file=${component_entry#file:}
      [[ -n $relative_file && $relative_file != / && $relative_file != /* && $relative_file != .. && $relative_file != *../* && $relative_file != ../* && $relative_file != */.. ]] || {
        print -u2 -- "error: invalid path in Rust component $component: $relative_file"
        exit 1
      }
      [[ -f ${toolchain_root}/${relative_file} ]] || {
        print -u2 -- "error: file from Rust component $component is unavailable: $relative_file"
        exit 1
      }
      file_sha256=$(sha256sum ${toolchain_root}/${relative_file})
      print -rn -- "${relative_file}\0${file_sha256%% *}\0"
    done < ${toolchain_root}/${component_manifest}
  done | sort -z | sha256sum
)
actual_components_sha256=${actual_components_sha256%% *}
[[ $actual_components_sha256 == ${locked[required_components_sha256]} ]] || {
  print -u2 -- "error: required Rust components digest is $actual_components_sha256; expected ${locked[required_components_sha256]}"
  exit 1
}

print -r -- "${locked[toolchain]} ${locked[required_components_sha256]}"
