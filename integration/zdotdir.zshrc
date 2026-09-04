if (( ${+WSH_STARTUP_BUNDLE_ZDOTDIR} )); then
  ZDOTDIR=$WSH_USER_ZDOTDIR
  typeset -g WSH_STARTUP_FILE=$ZDOTDIR/.zshrc
  if [[ $WSH_STARTUP_RCS == on && $WSH_STARTUP_FILE != $WSH_STARTUP_BUNDLE_ZDOTDIR/.zshrc && ( -e $WSH_STARTUP_FILE || -L $WSH_STARTUP_FILE ) ]]; then
    source $WSH_STARTUP_FILE
    WSH_STARTUP_RCS=$options[rcs]
  fi
  WSH_USER_ZDOTDIR=$ZDOTDIR
  unset WSH_STARTUP_FILE
fi

if [[ -n ${WSH_BUNDLE_ROOT:-} ]]; then
  typeset WSH_STARTUP_MODULE_PATH=${WSH_BUNDLE_ROOT}/lib/zsh/${ZSH_VERSION}
  typeset WSH_STARTUP_FUNCTION_PATH=${WSH_BUNDLE_ROOT}/share/zsh/${ZSH_VERSION}/functions
  module_path=("$WSH_STARTUP_MODULE_PATH" "${(@)module_path:#${(b)WSH_STARTUP_MODULE_PATH}}")
  fpath=("$WSH_STARTUP_FUNCTION_PATH" "${(@)fpath:#${(b)WSH_STARTUP_FUNCTION_PATH}}")
  unset WSH_STARTUP_MODULE_PATH WSH_STARTUP_FUNCTION_PATH
  if [[ ${WSH_RUN_FOREGROUND:-0} == prepared ]]; then
    autoload -Uz add-zsh-hook
    _wsh_run_foreground_startup() {
      builtin emulate -L zsh -o no_aliases
      add-zsh-hook -d precmd _wsh_run_foreground_startup
      local -a foreground_command=("${_WSH_FOREGROUND_ARGV[@]}")
      unset _WSH_FOREGROUND_ARGV WSH_RUN_FOREGROUND
      unfunction _wsh_run_foreground_startup
      if (( $#foreground_command == 0 )); then
        print -u2 -- 'wsh: foreground command is unavailable'
        return 127
      fi
      local extension extension_name
      local -i output_markers=1
      for extension in "${.term.extensions[@]}"; do
        extension_name=${extension#-}
        if [[ $extension_name == integration || $extension_name == integration-output ]]; then
          if [[ $extension == -* ]]; then
            output_markers=0
          else
            output_markers=1
          fi
          break
        fi
      done
      (( output_markers )) && print -nr -- $'\e]133;C\e\\' >| /dev/tty
      "$foreground_command[@]"
      local -i foreground_status=$?
      (( output_markers )) && print -nr -- $'\e]133;D\e\\' >| /dev/tty
      return $foreground_status
    }
    add-zsh-hook precmd _wsh_run_foreground_startup
    precmd_functions=(_wsh_run_foreground_startup "${(@)precmd_functions:#_wsh_run_foreground_startup}")
  fi
  source "${WSH_BUNDLE_ROOT}/share/wsh/defaults/history-substring-search.zsh"
  source "${WSH_BUNDLE_ROOT}/share/wsh/defaults/autosuggestions.zsh"
  if [[ ${WSH_DISABLE_SYNTAX_HIGHLIGHTING:-0} == 1 ]]; then
    typeset -g WSH_SYNTAX_HIGHLIGHTING_OWNER=disabled
  else
    source "${WSH_BUNDLE_ROOT}/share/wsh/defaults/syntax-highlighting.zsh"
  fi
  source "${WSH_BUNDLE_ROOT}/share/wsh/integration.zsh"
fi

if (( ${+WSH_STARTUP_BUNDLE_ZDOTDIR} )); then
  if [[ -o login ]]; then
    setopt rcs
    ZDOTDIR=$WSH_STARTUP_BUNDLE_ZDOTDIR
  else
    ZDOTDIR=$WSH_USER_ZDOTDIR
    [[ $WSH_STARTUP_RCS == on ]] || unsetopt rcs
    unset WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  fi
fi
