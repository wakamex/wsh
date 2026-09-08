typeset -gx WSH_BUNDLE_ROOT WSH_RUNTIME=$WSH_BUNDLE_ROOT/bin/wsh-runtime
typeset -gx WSH_NATIVE_TERMINAL_INTEGRATION=1
unset WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS WSH_RUN_FOREGROUND
# The prompt choice belongs to this shell, not to child shells.
(( ${+WSH_THEME} )) && typeset -g +x WSH_THEME

# User startup can load ZLE through completion initialization.
if [[ $ZSH_VERSION == 5.9.999.3-test && ${WSH_ENABLE_ZLE_TERMINAL_QUERY:-0} != 1 && ! -v .term.extensions ]]; then
  typeset -ga .term.extensions=(-query)
fi
if [[ -n ${WSH_PROFILE_FILE:-} && -r ${WSH_BUNDLE_ROOT}/share/wsh/profile.zsh ]]; then
  source ${WSH_BUNDLE_ROOT}/share/wsh/profile.zsh
fi
