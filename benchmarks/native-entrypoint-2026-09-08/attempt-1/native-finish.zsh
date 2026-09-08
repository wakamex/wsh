# Compatibility metadata for existing manager diagnostics and tests.
typeset -g WSH_USER_ZDOTDIR=${ZDOTDIR-$HOME}
(( ${+WSH_THEME} )) && typeset -g +x WSH_THEME
(( $+functions[_wsh_profile_event] )) && _wsh_profile_event bundle-zshenv-end
