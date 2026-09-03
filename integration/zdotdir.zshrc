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
  typeset WSH_STARTUP_MODULE_PATH=${WSH_BUNDLE_ROOT}/lib/zsh/5.9.2
  typeset WSH_STARTUP_FUNCTION_PATH=${WSH_BUNDLE_ROOT}/share/zsh/5.9.2/functions
  module_path=("$WSH_STARTUP_MODULE_PATH" "${(@)module_path:#${(b)WSH_STARTUP_MODULE_PATH}}")
  fpath=("$WSH_STARTUP_FUNCTION_PATH" "${(@)fpath:#${(b)WSH_STARTUP_FUNCTION_PATH}}")
  unset WSH_STARTUP_MODULE_PATH WSH_STARTUP_FUNCTION_PATH
  source "${WSH_BUNDLE_ROOT}/share/wsh/defaults/history-substring-search.zsh"
  source "${WSH_BUNDLE_ROOT}/share/wsh/defaults/autosuggestions.zsh"
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
