# Keep one owner for directory jumping, including custom command names.
typeset -g WSH_DIRECTORY_JUMP_OWNER=disabled
typeset -gi WSH_DIRECTORY_JUMP_REPLACED=0


_wsh_directory_takeover() {
  builtin emulate -L zsh -o no_aliases
  local jump_command=$1
  [[ ${aliases[$jump_command]:-} == 'zshz 2>&1' ]] || return 1
  [[ $jump_command == zshz ]] || (( ! ${+functions[$jump_command]} )) || return 1
  zmodload zsh/parameter || return 1
  local source=${functions_source[zshz]:-} function_name
  [[ -n $source ]] || return 1
  local reference=$WSH_BUNDLE_ROOT/share/wsh/defaults/zsh-z
  [[ -r $reference/takeover.zsh ]] || return 1
  _wsh_plugin_recognized directory $source || return 1
  # Query-local helpers are redefined on every upstream call; their source
  # metadata names the caller. Check the persistent public/lifecycle functions.
  for function_name in _zshz_usage _zshz_realpath _zshz_precmd _zshz_chpwd _zshz_zle_completion_widget zsh-z_plugin_unload; do
    [[ ${functions_source[$function_name]:-} == $source ]] || return 1
  done
  source $reference/takeover.zsh || return 1
  WSH_DIRECTORY_JUMP_OWNER=wsh
  WSH_DIRECTORY_JUMP_REPLACED=1
}
_wsh_load_directory_jump() {
  builtin emulate -L zsh -o no_aliases
  [[ ${WSH_DISABLE_DIRECTORY_JUMP:-0} == 1 ]] && return 0
  local jump_command=${ZSHZ_CMD:-${_Z_CMD:-z}}
  if (( $+aliases[$jump_command] || $+functions[$jump_command] || $+functions[zshz] || $+functions[_z] )) || builtin whence -w -- "$jump_command" >/dev/null; then
    WSH_DIRECTORY_JUMP_OWNER=external
    _wsh_directory_takeover "$jump_command" || true
    return 0
  fi
  if [[ -r $WSH_BUNDLE_ROOT/share/wsh/defaults/zsh-z/native.zsh ]]; then
    source "$WSH_BUNDLE_ROOT/share/wsh/defaults/zsh-z/native.zsh"
  else
    source "$WSH_BUNDLE_ROOT/share/wsh/defaults/zsh-z/z.plugin.zsh"
  fi
  autoload -Uz _zshz
  if (( $+functions[compdef] )); then
    compdef _zshz zshz "$jump_command"
  fi
  WSH_DIRECTORY_JUMP_OWNER=wsh
}
_wsh_load_directory_jump
unfunction _wsh_load_directory_jump _wsh_directory_takeover
