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
