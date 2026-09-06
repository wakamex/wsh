# The launcher setting belongs to this shell, not to child shells.
typeset -g +x WSH_PROMPT=${WSH_PROMPT:-existing}

if [[ ${WSH_RUN_FOREGROUND:-0} == 1 ]]; then
  typeset -ga _WSH_FOREGROUND_ARGV=("$@")
  set --
  typeset -g WSH_RUN_FOREGROUND=prepared
fi

if [[ -n ${WSH_PROFILE_FILE:-} && -n ${WSH_BUNDLE_ROOT:-} && -r ${WSH_BUNDLE_ROOT}/share/wsh/profile.zsh ]]; then
  source ${WSH_BUNDLE_ROOT}/share/wsh/profile.zsh
fi

if [[ -n ${WSH_BUNDLE_ROOT:-} ]]; then
  typeset WSH_STARTUP_MODULE_PATH=${WSH_BUNDLE_ROOT}/lib/zsh/${ZSH_VERSION}
  typeset WSH_STARTUP_FUNCTION_PATH=${WSH_BUNDLE_ROOT}/share/zsh/${ZSH_VERSION}/functions
  module_path=("$WSH_STARTUP_MODULE_PATH" "${(@)module_path:#${(b)WSH_STARTUP_MODULE_PATH}}")
  fpath=("$WSH_STARTUP_FUNCTION_PATH" "${(@)fpath:#${(b)WSH_STARTUP_FUNCTION_PATH}}")
  unset WSH_STARTUP_MODULE_PATH WSH_STARTUP_FUNCTION_PATH
fi

if (( ${+WSH_USER_ZDOTDIR} )); then
  typeset -g WSH_STARTUP_BUNDLE_ZDOTDIR=$ZDOTDIR
  typeset -g WSH_STARTUP_RCS=$options[rcs]
  typeset -g ZDOTDIR=$WSH_USER_ZDOTDIR
  typeset -g WSH_STARTUP_FILE=$ZDOTDIR/.zshenv
  if [[ $WSH_STARTUP_FILE != $WSH_STARTUP_BUNDLE_ZDOTDIR/.zshenv && ( -e $WSH_STARTUP_FILE || -L $WSH_STARTUP_FILE ) ]]; then
    (( $+functions[_wsh_profile_event] )) && _wsh_profile_event user-zshenv-start
    source $WSH_STARTUP_FILE
    (( $+functions[_wsh_profile_event] )) && _wsh_profile_event user-zshenv-end
    WSH_STARTUP_RCS=$options[rcs]
  fi
  WSH_USER_ZDOTDIR=$ZDOTDIR
  unset WSH_STARTUP_FILE
  if [[ -o interactive || -o login ]]; then
    setopt rcs
    ZDOTDIR=$WSH_STARTUP_BUNDLE_ZDOTDIR
  else
    ZDOTDIR=$WSH_USER_ZDOTDIR
    [[ $WSH_STARTUP_RCS == on ]] || unsetopt rcs
    unset WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  fi
fi

(( $+functions[_wsh_profile_event] )) && _wsh_profile_event bundle-zshenv-end

if [[ $ZSH_VERSION == 5.9.999.3-test && ${WSH_ENABLE_ZLE_TERMINAL_QUERY:-0} != 1 && ! -v .term.extensions ]]; then
  typeset -ga .term.extensions=(-query)
fi
