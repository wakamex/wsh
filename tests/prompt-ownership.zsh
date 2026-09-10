#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect
(( $# == 1 || $# == 2 )) || {
  print -u2 -- 'usage: prompt-ownership.zsh BUNDLE [REAL_OMZ_DIRECTORY]'
  exit 2
}
readonly bundle=${1:A} omz=${2:-}
readonly scratch=$(mktemp -d /var/tmp/wsh-prompt-ownership.XXXXXX)
readonly state=$scratch/state
readonly home=$scratch/home
readonly custom_theme="$scratch/custom theme.toml"
local current_pty= output= mode= kind= login_flag=
cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $scratch
}
trap cleanup EXIT INT TERM
mkdir -p $home
sed 's/^id = "minimal"$/id = "custom-selection"/' $bundle/share/wsh/themes/minimal.toml > $custom_theme
print -r -- 'theme-version = "invalid"' > $scratch/invalid.toml
python3 "${0:A:h:h}/build/native_manifest.py" verify $bundle >/dev/null
cat > $home/.zshenv <<'CONFIG'
typeset -g selector_at_zshenv=${WSH_THEME-absent}
CONFIG
cat > $home/.zshrc <<'CONFIG'
typeset -g selector_at_zshrc=${WSH_THEME-absent}
ZSH_THEME=robbyrussell
if [[ -n ${WSH_THEME-} ]]; then
  ZSH_THEME=""
fi
if [[ -n ${WSH_TEST_OMZ:-} ]]; then
  ZSH=$WSH_TEST_OMZ
  ZSH_CACHE_DIR=$HOME/cache
  ZSH_COMPDUMP=$HOME/.zcompdump
  zstyle ':omz:update' mode disabled
  ZSH_DISABLE_COMPFIX=true
  plugins=(git)
  source "$ZSH/oh-my-zsh.sh"
else
  PROMPT='EXISTING> '
  RPROMPT='existing-right'
fi
alias user_alias='print -r -- alias-preserved'
autoload -Uz add-zsh-hook
typeset -gi user_hook_count=0
user_precmd() { (( user_hook_count++ )); return 0; }
add-zsh-hook precmd user_precmd
typeset -g saved_prompt=$PROMPT saved_rprompt=$RPROMPT
# Wsh must revoke user startup exports before launching nested regular Zsh.
(( ${+WSH_THEME} )) && export WSH_THEME
true
CONFIG
cat > $home/.zlogin <<'CONFIG'
typeset -g selector_at_zlogin=${WSH_THEME-absent}
(( ${+WSH_THEME} )) && export WSH_THEME
true
CONFIG
cat > $scratch/probe.zsh <<'CONFIG'
[[ ${WSH_PROMPT_OWNER:-existing} == ${EXPECT_OWNER:-existing} ]] || return 10
[[ $selector_at_zshenv == $EXPECT_SELECTOR && $selector_at_zshrc == $EXPECT_SELECTOR ]] || return 11
[[ ${selector_at_zlogin-$EXPECT_SELECTOR} == $EXPECT_SELECTOR ]] || return 12
(( user_hook_count > 0 )) || return 13
if [[ -n ${WSH_TEST_OMZ:-} ]]; then
  (( $+functions[_omz_source] && $+aliases[g] )) || return 21
fi
[[ $aliases[user_alias] == 'print -r -- alias-preserved' ]] || return 14
if [[ ${WSH_PROMPT_OWNER:-existing} == wsh ]]; then
  [[ $WSH_RUNTIME_READY == 1 && -n $WSH_RUNTIME_PID && -z $ZSH_THEME ]] || return 15
  [[ $PROMPT == $WSH_LAST_PROMPT && $RPROMPT == $WSH_LAST_RPROMPT ]] || return 20
  typeset -a prompt_hooks=("${(@M)precmd_functions:#_wsh_runtime_precmd}")
  (( ${#prompt_hooks} == 1 )) || return 16
else
  [[ -z ${WSH_RUNTIME_PID:-} && ${WSH_RUNTIME_READY:-0} == 0 ]] || return 17
  [[ ${precmd_functions[(Ie)_wsh_runtime_precmd]} == 0 ]] || return 22
  [[ $PROMPT == $saved_prompt && $RPROMPT == $saved_rprompt ]] || return 18
fi
# The selector must not cross exec into ordinary nested Zsh.
[[ $($WSH_TEST_ZSH -dic 'print -r -- NESTED:${WSH_THEME-absent}:$ZSH_THEME') == *NESTED:absent:robbyrussell* ]] || return 19
print -r -- OWNERSHIP_OK
CONFIG

child() {
  export HOME=$home ZDOTDIR=$home TERM=xterm-256color WSH_STATE_ROOT=$state
  export WSH_TEST_ZSH=${WSH_REFERENCE_ZSH:-/usr/bin/zsh} WSH_TEST_OMZ=$omz
  unset WSH_THEME WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_INTEGRATION_LOADED WSH_PROMPT_OWNER
  case $mode in
    default|regular) export EXPECT_OWNER=existing EXPECT_SELECTOR=absent ;;
    minimal|profile-wsh) export WSH_THEME=minimal EXPECT_OWNER=wsh EXPECT_SELECTOR=minimal ;;
    wakamex|profile-wakamex) export WSH_THEME=wakamex EXPECT_OWNER=wsh EXPECT_SELECTOR=wakamex ;;
    path|profile-path) export WSH_THEME=$custom_theme EXPECT_OWNER=wsh EXPECT_SELECTOR=$custom_theme ;;
    empty|profile-existing) export WSH_THEME='' EXPECT_OWNER=existing EXPECT_SELECTOR='' ;;
    missing) export WSH_THEME=$scratch/missing.toml EXPECT_OWNER=existing EXPECT_SELECTOR=$scratch/missing.toml ;;
    invalid) export WSH_THEME=$scratch/invalid.toml EXPECT_OWNER=existing EXPECT_SELECTOR=$scratch/invalid.toml ;;
  esac
  command stty -echo
  if [[ $mode == profile-* ]]; then
    exec $bundle/bin/wsh --wsh-profile -- -d
  elif [[ $mode == regular ]]; then
    exec $WSH_TEST_ZSH -di ${=login_flag}
  else
    exec $bundle/bin/wsh -d -di ${=login_flag}
  fi
}
wait_for() {
  local expected=$1 chunk
  local -F deadline=$(( EPOCHREALTIME + 8 ))
  while (( EPOCHREALTIME < deadline )); do
    while zpty -r -t $current_pty chunk 2>/dev/null; do output+=$chunk; done
    [[ $output == *$expected* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -r -- "FAIL: $mode $login_flag waiting for ${(qqq)expected}: ${(qqq)output}"
  return 1
}
for login_flag in '' -l; do
  for mode in regular default empty minimal wakamex path missing invalid profile-existing profile-wsh profile-wakamex profile-path; do
    [[ -n $login_flag && $mode == profile-* ]] && continue
    output=
    current_pty=wsh_ownership_${$}
    zpty -b $current_pty child
    wait_for $'\e]133;B\e\\'
    zpty -w $current_pty "source ${(q)scratch}/probe.zsh; print -r -- PROBE_STATUS:\$?"
    wait_for $'\r\nPROBE_STATUS:'
    [[ $output == *OWNERSHIP_OK* && $output == *PROBE_STATUS:0* ]] || {
      print -u2 -r -- "FAIL: $mode $login_flag ${(qqq)output}"
      exit 1
    }
    if [[ $mode == invalid || $mode == missing ]]; then
      [[ $output == *'could not start the selected theme; preserving the existing prompt'* ]] || exit 1
    fi
    zpty -w $current_pty exit
    if [[ $mode == profile-* ]]; then
      wait_for $'\r\nStartup\r\n'
      profile_dirs=($state/profiles/*(/om[1]))
      report=$($bundle/bin/wsh --wsh-profile-report $profile_dirs[1])
      [[ $report == *'Wsh ZLE initialization hook:'* ]] || exit 1
      if [[ $mode == profile-existing ]]; then
        ! grep -q '"source":"runtime"' $profile_dirs[1]/trace.jsonl
      else
        grep -q '"source":"runtime"' $profile_dirs[1]/trace.jsonl
        case $mode in
          profile-wsh) [[ $report == *'Theme: minimal'* ]] ;;
          profile-wakamex) [[ $report == *'Theme: wakamex'* ]] ;;
          profile-path) [[ $report == *'Theme: custom-selection'* ]] ;;
        esac
      fi
    fi
    zselect -t 5 2>/dev/null || true
    zpty -d $current_pty 2>/dev/null || true
    current_pty=
    print -r -- "PASS: ${mode} ${login_flag:-non-login} prompt ownership, startup selector, hooks and nested regular Zsh"
  done
done

if [[ -n $omz ]]; then
  [[ -r $omz/oh-my-zsh.sh ]] || exit 2
  # First reproduce overlap without the conditional, using the real OMZ loader.
  cp $home/.zshrc $scratch/conditional.zshrc
  sed '/^if \[\[ -n ${WSH_THEME-} \]\]; then$/,/^fi$/d' $scratch/conditional.zshrc > $home/.zshrc
  before=$(sha256sum $home/.zshrc)
  report=$(HOME=$home ZDOTDIR=$home WSH_TEST_OMZ=$omz WSH_THEME=minimal $bundle/bin/wsh --wsh-doctor)
  [[ $report == *'before sourcing oh-my-zsh.sh'* && $report == *'alone does not skip'* ]]
  [[ $(sha256sum $home/.zshrc) == $before ]]
  report=$(HOME=$home ZDOTDIR=$home WSH_TEST_OMZ=$omz WSH_THEME= $bundle/bin/wsh --wsh-doctor)
  [[ $report != *'Prompt compatibility:'* ]]
  cp $scratch/conditional.zshrc $home/.zshrc
  before=$(sha256sum $home/.zshrc)
  report=$(HOME=$home ZDOTDIR=$home WSH_TEST_OMZ=$omz WSH_THEME=minimal $bundle/bin/wsh --wsh-doctor)
  [[ $report != *'Prompt compatibility:'* && $(sha256sum $home/.zshrc) == $before ]]
  print -r -- 'PASS: real OMZ overlap advice, conditional resolution, existing-mode silence, unchanged configuration'
else
  print -r -- 'Real OMZ checks require the optional directory argument.'
fi
