# Transitional compatibility with the unchanged Rust management commands.
if [[ ${ZDOTDIR-} == $WSH_BUNDLE_ROOT/share/wsh/zdotdir ]]; then
  if (( ${+WSH_USER_ZDOTDIR} )); then
    ZDOTDIR=$WSH_USER_ZDOTDIR
  else
    unset ZDOTDIR
  fi
fi
typeset -gx WSH_BUNDLE_ROOT WSH_RUNTIME=$WSH_BUNDLE_ROOT/bin/wsh-runtime
typeset -gx WSH_NATIVE_TERMINAL_INTEGRATION=1
unset WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
# The launcher setting belongs to this shell, not to child shells.
(( ${+WSH_THEME} )) && typeset -g +x WSH_THEME

# User startup can load ZLE through completion initialization.
if [[ $ZSH_VERSION == 5.9.999.3-test && ${WSH_ENABLE_ZLE_TERMINAL_QUERY:-0} != 1 && ! -v .term.extensions ]]; then
  typeset -ga .term.extensions=(-query)
fi

if [[ ${WSH_RUN_FOREGROUND:-0} == 1 ]]; then
  typeset -ga _WSH_FOREGROUND_ARGV=("$@")
  set --
  typeset -g WSH_RUN_FOREGROUND=prepared
fi

if [[ -n ${WSH_BUNDLE_ROOT:-} ]]; then
  typeset WSH_STARTUP_MODULE_PATH=${WSH_BUNDLE_ROOT}/lib/zsh/${ZSH_VERSION}
  typeset WSH_STARTUP_FUNCTION_PATH=${WSH_BUNDLE_ROOT}/share/zsh/${ZSH_VERSION}/functions
  module_path=("$WSH_STARTUP_MODULE_PATH" "${(@)module_path:#${(b)WSH_STARTUP_MODULE_PATH}}")
  fpath=("$WSH_STARTUP_FUNCTION_PATH" "${(@)fpath:#${(b)WSH_STARTUP_FUNCTION_PATH}}")
  unset WSH_STARTUP_MODULE_PATH WSH_STARTUP_FUNCTION_PATH
fi

if [[ -n ${WSH_PROFILE_FILE:-} && -n ${WSH_BUNDLE_ROOT:-} && -r ${WSH_BUNDLE_ROOT}/share/wsh/profile.zsh ]]; then
  source ${WSH_BUNDLE_ROOT}/share/wsh/profile.zsh
fi

