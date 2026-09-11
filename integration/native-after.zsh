source "$WSH_BUNDLE_ROOT/share/wsh/defaults/plugin-recognition.zsh"
(( $+functions[_wsh_profile_event] )) && _wsh_profile_event directory-jump-start
source "${WSH_BUNDLE_ROOT}/share/wsh/defaults/directory-jump.zsh"
(( $+functions[_wsh_profile_event] )) && _wsh_profile_event directory-jump-end
(( $+functions[_wsh_profile_event] )) && _wsh_profile_event history-start
source "${WSH_BUNDLE_ROOT}/share/wsh/defaults/history-substring-search.zsh"
(( $+functions[_wsh_profile_event] )) && _wsh_profile_event history-end
(( $+functions[_wsh_profile_event] )) && _wsh_profile_event autosuggestions-start
source "${WSH_BUNDLE_ROOT}/share/wsh/defaults/autosuggestions.zsh"
(( $+functions[_wsh_profile_event] )) && _wsh_profile_event autosuggestions-end
(( $+functions[_wsh_profile_event] )) && _wsh_profile_event syntax-highlighting-start
if [[ ${WSH_DISABLE_SYNTAX_HIGHLIGHTING:-0} == 1 ]]; then
  typeset -g WSH_SYNTAX_HIGHLIGHTING_OWNER=disabled
else
  source "${WSH_BUNDLE_ROOT}/share/wsh/defaults/syntax-highlighting.zsh"
fi
(( $+functions[_wsh_profile_event] )) && _wsh_profile_event syntax-highlighting-end
(( $+functions[_wsh_profile_event] )) && _wsh_profile_event integration-start
source "${WSH_BUNDLE_ROOT}/share/wsh/integration.zsh"
source "${WSH_BUNDLE_ROOT}/share/wsh/defaults/git-prompt.zsh"
(( $+functions[_wsh_profile_event] )) && _wsh_profile_event integration-end
(( $+functions[_wsh_profile_install] )) && _wsh_profile_install
unset _WSH_PLUGIN_REFERENCES _WSH_PLUGIN_UPSTREAMS _WSH_PLUGIN_HANDOFF
unfunction _wsh_plugin_recognized _wsh_plugin_files_equal _wsh_plugin_git_recognized _wsh_plugin_git
