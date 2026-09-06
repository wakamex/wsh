# Keep one owner for directory jumping, including custom command names.
typeset -g WSH_DIRECTORY_JUMP_OWNER=disabled
_wsh_load_directory_jump() {
  builtin emulate -L zsh -o no_aliases
  [[ ${WSH_DISABLE_DIRECTORY_JUMP:-0} == 1 ]] && return 0
  local jump_command=${ZSHZ_CMD:-${_Z_CMD:-z}}
  if (( $+aliases[$jump_command] || $+functions[$jump_command] || $+commands[$jump_command] || $+functions[zshz] || $+functions[_z] )); then
    WSH_DIRECTORY_JUMP_OWNER=external
    return 0
  fi
  source "$WSH_BUNDLE_ROOT/share/wsh/defaults/zsh-z/z.plugin.zsh"
  autoload -Uz _zshz
  if (( $+functions[compdef] )); then
    compdef _zshz zshz "$jump_command"
  fi
  WSH_DIRECTORY_JUMP_OWNER=wsh
}
_wsh_load_directory_jump
unfunction _wsh_load_directory_jump
