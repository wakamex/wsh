# Compatibility metadata for existing manager diagnostics and tests.
typeset -g WSH_USER_ZDOTDIR=${ZDOTDIR-$HOME}
(( ${+WSH_THEME} )) && typeset -g +x WSH_THEME
