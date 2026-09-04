#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

(( $# == 1 )) || {
  print -u2 -- 'usage: benchmark-edge-zsh-memory.zsh BUNDLE'
  exit 2
}

readonly root=${0:A:h:h}
readonly bundle=${1:A}
[[ -x $bundle/bin/zsh && -x $bundle/bin/wsh-runtime ]] || {
  print -u2 -- "error: incomplete bundle: $bundle"
  exit 2
}
readonly zsh_version=$($bundle/bin/zsh -fc 'print -r -- $ZSH_VERSION')
[[ -d $bundle/lib/zsh/$zsh_version && -d $bundle/share/zsh/$zsh_version/functions ]] || {
  print -u2 -- "error: versioned Zsh payload is incomplete: $zsh_version"
  exit 2
}

readonly adapter=$(mktemp -d /var/tmp/wsh-edge-memory-adapter.XXXXXX)
cleanup() {
  command rm -rf -- $adapter
}
trap cleanup EXIT INT TERM
command mkdir -p -- $adapter/lib/zsh $adapter/share/zsh/5.9.2
command ln -s -- $bundle/lib/zsh/$zsh_version $adapter/lib/zsh/5.9.2
command ln -s -- $bundle/share/zsh/$zsh_version/functions $adapter/share/zsh/5.9.2/functions

WSH_MEMORY_ZSH=$bundle/bin/zsh \
WSH_MEMORY_RUNTIME=$bundle/bin/wsh-runtime \
WSH_MEMORY_INTEGRATION=$bundle/share/wsh/integration.zsh \
WSH_MEMORY_THEME=$root/benchmarks/wsh-benchmark.toml \
WSH_MEMORY_BUNDLE_ROOT=$adapter \
  $root/benchmarks/benchmark-runtime-memory.zsh
