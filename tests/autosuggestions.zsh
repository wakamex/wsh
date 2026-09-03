#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 2 || $# == 4 )) || {
  print -u2 -- 'usage: autosuggestions.zsh MANAGER BUNDLE [AUTOSUGGESTIONS-REPOSITORY SYNTAX-HIGHLIGHTING-REPOSITORY]'
  exit 2
}

readonly manager=${1:A}
readonly bundle=${2:A}
readonly autosuggestions_repository=${3:-}
readonly syntax_repository=${4:-}
readonly external_sources=$(( $# == 4 ))
readonly autosuggestions_revision=85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5
readonly syntax_revision=2fc57d63067c18b1100ecdbf684fa5baf49459d1
[[ -x $manager && -x $bundle/bin/zsh ]] || {
  print -u2 -- 'error: manager or bundle is invalid'
  exit 2
}
if (( external_sources )); then
  git -C ${autosuggestions_repository:A} cat-file -e ${autosuggestions_revision}^{commit} 2>/dev/null || exit 2
  git -C ${syntax_repository:A} cat-file -e ${syntax_revision}^{commit} 2>/dev/null || exit 2
fi

readonly test_root=$(mktemp -d /var/tmp/wsh-autosuggestions-correctness.XXXXXX)
readonly state_root=$test_root/state
readonly fixture=$test_root/fixture
readonly autosuggestions_source=$test_root/autosuggestions
readonly syntax_source=$test_root/syntax
typeset -g current_pty= pty_output= child_home= child_suggestion_log= child_buffer_log= child_state_log=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $test_root
}
trap cleanup EXIT INT TERM

command mkdir -p -- $state_root $fixture $autosuggestions_source $syntax_source
if (( external_sources )); then
  git -C ${autosuggestions_repository:A} archive $autosuggestions_revision | tar -xf - -C $autosuggestions_source
  git -C ${syntax_repository:A} archive $syntax_revision | tar -xf - -C $syntax_source
else
  command cp -- $bundle/share/wsh/defaults/zsh-autosuggestions.zsh $autosuggestions_source/zsh-autosuggestions.zsh
fi
$manager bundle activate $bundle --state-root $state_root >/dev/null
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh autosuggestions correctness test'
git -C $fixture config user.email autosuggestions-correctness@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial

write_home() {
  local variant=$1
  local home=$test_root/home-$variant
  command mkdir -p -- $home
  local config=$home/.zshrc
  print -r -- 'setopt hist_ignore_space
print -s "print -r -- WSH_AUTOSUGGEST_OLDER"
print -s "print -r -- WSH_AUTOSUGGEST_COMPLETE"
autoload -Uz add-zle-hook-widget
_wsh_test_capture_suggestion() {
  [[ -z $POSTDISPLAY ]] || print -r -- "$BUFFER|$POSTDISPLAY" >> $WSH_TEST_SUGGESTION_LOG
}
_wsh_test_report_buffer() {
  print -r -- "$BUFFER|$POSTDISPLAY" >> $WSH_TEST_BUFFER_LOG
  BUFFER=""
  POSTDISPLAY=""
  zle .accept-line
}
_wsh_test_report_state() {
  zmodload zsh/parameter zsh/zleparameter
  local source=${functions_source[_zsh_autosuggest_start]:-none}
  local start_count=${#${(M)precmd_functions:#_zsh_autosuggest_start}}
  local -a redraw_hooks=()
  zstyle -a zle-line-pre-redraw widgets redraw_hooks
  local syntax_count=${#${(M)redraw_hooks:#*:_zsh_highlight__zle-line-pre-redraw}}
  local child_state=reaped
  [[ -n ${_ZSH_AUTOSUGGEST_CHILD_PID:-} ]] && kill -0 $_ZSH_AUTOSUGGEST_CHILD_PID 2>/dev/null && child_state=live
  print -r -- "${WSH_AUTOSUGGESTIONS_OWNER-unset}|${WSH_AUTOSUGGESTIONS_REPLACED-unset}|${source}|${start_count}|${+ZSH_AUTOSUGGEST_MANUAL_REBIND}|${_ZSH_AUTOSUGGEST_ASYNC_FD:-}|${_ZSH_AUTOSUGGEST_CHILD_PID:-}|${ZSH_AUTOSUGGEST_VERSION-unset}|${ZSH_HIGHLIGHT_VERSION-unset}|${syntax_count}|${ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE-unset}|${(j:,:)ZSH_AUTOSUGGEST_STRATEGY}|${ZSH_AUTOSUGGEST_BUFFER_MAX_SIZE-unset}|${widgets[self-insert]-unset}|${#_ZSH_AUTOSUGGEST_BIND_COUNTS}|${history[(r)print -r -- WSH_AUTOSUGGEST_COMPLETE]-missing}|${POSTDISPLAY}|${child_state}|${(j:,:)ZSH_AUTOSUGGEST_ACCEPT_WIDGETS}|${(j:,:)ZSH_AUTOSUGGEST_CLEAR_WIDGETS}|${(j:,:)ZSH_AUTOSUGGEST_IGNORE_WIDGETS}|${ZSH_AUTOSUGGEST_COMPLETION_IGNORE-unset}|${+ZSH_AUTOSUGGEST_USE_ASYNC}|${ZSH_AUTOSUGGEST_MANUAL_REBIND-unset}" >> $WSH_TEST_STATE_LOG
}
_wsh_test_custom_widget() {
  BUFFER+="CUSTOM"
  CURSOR=$#BUFFER
}
zle -N _wsh_test_report_buffer
zle -N _wsh_test_report_state
zle -N _wsh_test_custom_widget
bindkey -M emacs '^G' _wsh_test_report_buffer
bindkey -M emacs '^T' _wsh_test_report_state
bindkey -M emacs '^X' _wsh_test_custom_widget
add-zle-hook-widget zle-line-pre-redraw _wsh_test_capture_suggestion' >| $config

  case $variant in
    clean) ;;
    external)
      print -r -- "source ${(q)autosuggestions_source}/zsh-autosuggestions.zsh" >> $config
      ;;
    external-active)
      print -r -- "source ${(q)autosuggestions_source}/zsh-autosuggestions.zsh
_zsh_autosuggest_start" >> $config
      ;;
    unknown)
      print -r -- '_zsh_autosuggest_start() { : }
_zsh_autosuggest_bind_widgets() { : }
zle -N autosuggest-fetch _wsh_test_custom_widget' >> $config
      ;;
    disabled)
      print -r -- 'typeset -g WSH_DISABLE_AUTOSUGGESTIONS=1' >> $config
      ;;
    configured)
      print -r -- 'typeset -g ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE=fg=blue
typeset -ga ZSH_AUTOSUGGEST_STRATEGY=(history)
typeset -g ZSH_AUTOSUGGEST_BUFFER_MAX_SIZE=1234
typeset -ga ZSH_AUTOSUGGEST_ACCEPT_WIDGETS=(end-of-line)
typeset -ga ZSH_AUTOSUGGEST_CLEAR_WIDGETS=(accept-line)
typeset -ga ZSH_AUTOSUGGEST_IGNORE_WIDGETS=(beep)
typeset -g ZSH_AUTOSUGGEST_COMPLETION_IGNORE="git *"
typeset -g ZSH_AUTOSUGGEST_MANUAL_REBIND=configured
typeset -g WSH_AUTOSUGGEST_ASYNC=0' >> $config
      ;;
    composition)
      print -r -- "source ${(q)syntax_source}/zsh-syntax-highlighting.zsh" >> $config
      ;;
  esac
}

pty_read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

pty_wait_for_prompt() {
  local label=${1:-prompt}
  local -F deadline=$(( EPOCHREALTIME + 5 ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    [[ $pty_output == *git:main* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -r -- "timeout waiting for ${label}: ${(qqq)pty_output}"
  return 1
}

pty_wait_for_text() {
  local expected=$1 label=$2
  local -F deadline=$(( EPOCHREALTIME + 5 ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    [[ $pty_output == *$expected* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -r -- "timeout waiting for ${label}: ${(qqq)pty_output}"
  return 1
}

wait_for_lines() {
  local file=$1 expected=$2
  local -F deadline=$(( EPOCHREALTIME + 3 ))
  while (( EPOCHREALTIME < deadline )); do
    [[ -e $file && $(wc -l < $file) -ge $expected ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -- "timeout waiting for ${expected} lines in ${file}"
  return 1
}

managed_child() {
  builtin cd -q -- $fixture
  export HOME=$child_home
  export ZDOTDIR=$child_home
  export WSH_STATE_ROOT=$state_root
  export WSH_TEST_SUGGESTION_LOG=$child_suggestion_log
  export WSH_TEST_BUFFER_LOG=$child_buffer_log
  export WSH_TEST_STATE_LOG=$child_state_log
  export TERM=xterm-256color
  unset EDITOR VISUAL WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  exec $manager run --state-root $state_root
}

start_variant() {
  local variant=$1
  child_home=$test_root/home-$variant
  child_suggestion_log=$test_root/$variant-suggestion.log
  child_buffer_log=$test_root/$variant-buffer.log
  child_state_log=$test_root/$variant-state.log
  : >| $child_suggestion_log
  : >| $child_buffer_log
  : >| $child_state_log
  current_pty=wsh_autosuggestions_${variant//[^A-Za-z0-9]/_}_${$}
  pty_output=
  zpty -b $current_pty managed_child
  pty_wait_for_prompt startup-prompt
}

stop_variant() {
  zpty -w $current_pty exit
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
}

report_state() {
  local line_number=${1:-1}
  zpty -w -n $current_pty $'\x14'
  wait_for_lines $child_state_log $line_number
  sed -n "${line_number}p" $child_state_log
}

assert_suggestion() {
  pty_output=
  zpty -w -n $current_pty 'print -r -- WSH_AUTO'
  local -F deadline=$(( EPOCHREALTIME + 3 ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    [[ $pty_output == *SUGGEST_COMPLETE* ]] && break
    zselect -t 1 2>/dev/null || true
  done
  [[ $pty_output == *SUGGEST_COMPLETE* ]] || {
    print -u2 -r -- "suggestion did not appear: state=${(qqq)state} output=${(qqq)pty_output} log=${(qqq)$(<$child_suggestion_log)}"
    return 1
  }
  zpty -w -n $current_pty $'\x05\x07'
  wait_for_lines $child_buffer_log 1
  [[ $(sed -n '1p' $child_buffer_log) == 'print -r -- WSH_AUTOSUGGEST_COMPLETE|' ]] || {
    print -u2 -r -- "suggestion was not accepted: ${(qqq)$(<$child_buffer_log)}"
    return 1
  }
}

local -a variants=(clean external external-active unknown disabled configured)
(( external_sources )) && variants+=(composition)
local variant state
for variant in $variants; do
  write_home $variant
  start_variant $variant
  state=$(report_state)
  case $variant in
    clean|configured|composition)
      [[ $state == wsh\|0\|${bundle}/share/wsh/defaults/zsh-autosuggestions.zsh\|0\|1\|\|\|* ]] || { print -u2 -r -- "unexpected bundled state for ${variant}: $state"; exit 1; }
      ;;
    external)
      [[ $state == wsh\|1\|${bundle}/share/wsh/defaults/zsh-autosuggestions.zsh\|0\|1\|\|\|* ]] || { print -u2 -r -- "unexpected takeover state: $state"; exit 1; }
      ;;
    external-active)
      [[ $state == external-active\|0\|${autosuggestions_source}/zsh-autosuggestions.zsh\|1\|0\|\|\|* ]] || { print -u2 -r -- "unexpected active external state: $state"; exit 1; }
      ;;
    unknown)
      [[ $state == external-unknown\|0\|${child_home}/.zshrc\|0\|0\|\|\|* ]] || { print -u2 -r -- "unexpected unknown state: $state"; exit 1; }
      ;;
    disabled)
      [[ $state == disabled\|0\|none\|0\|0\|\|\|unset\|* ]] || { print -u2 -r -- "unexpected disabled state: $state"; exit 1; }
      ;;
  esac
  if [[ $variant == configured ]]; then
    [[ $state == *'|fg=blue|history|1234|'* ]] || { print -u2 -r -- "configuration was not preserved: $state"; exit 1; }
    [[ $state == *'|end-of-line|accept-line|beep|git *|0|configured' ]] || { print -u2 -r -- "widget or execution configuration was not preserved: $state"; exit 1; }
  fi
  if [[ $variant == composition ]]; then
    [[ $state == *'|0.8.1-dev|1|'* ]] || { print -u2 -r -- "syntax highlighting did not compose: $state"; exit 1; }
  fi
  if [[ $variant == clean || $variant == external || $variant == external-active || $variant == composition ]]; then
    assert_suggestion
  fi
  if [[ $variant == clean ]]; then
    zpty -w -n $current_pty A$'\x18\x07'
    wait_for_lines $child_buffer_log 2
    [[ $(sed -n '2p' $child_buffer_log) == ACUSTOM\|* ]] || { print -u2 -r -- "custom widget did not run through autosuggestions: ${(qqq)$(sed -n '2p' $child_buffer_log)}"; exit 1; }
    zpty -w -n $current_pty 'print -r -- WSH_AUTO'$'\e[A\x07'
    wait_for_lines $child_buffer_log 3
    [[ $(sed -n '3p' $child_buffer_log) == 'print -r -- WSH_AUTOSUGGEST_COMPLETE|' ]] || { print -u2 -r -- "history search did not select the newest match: ${(qqq)$(sed -n '3p' $child_buffer_log)}"; exit 1; }
    zpty -w -n $current_pty 'print -r -- WSH_AUTO'$'\e[A\e[A\x07'
    wait_for_lines $child_buffer_log 4
    [[ $(sed -n '4p' $child_buffer_log) == 'print -r -- WSH_AUTOSUGGEST_OLDER|' ]] || { print -u2 -r -- "history search did not navigate to the older match: ${(qqq)$(sed -n '4p' $child_buffer_log)}"; exit 1; }
    zpty -w -n $current_pty 'print -r -- WSH_AUTO'$'\e[A\e[A\e[B\x07'
    wait_for_lines $child_buffer_log 5
    [[ $(sed -n '5p' $child_buffer_log) == 'print -r -- WSH_AUTOSUGGEST_COMPLETE|' ]] || { print -u2 -r -- "history search did not navigate forward: ${(qqq)$(sed -n '5p' $child_buffer_log)}"; exit 1; }
    pty_output=
    pty_wait_for_prompt history-report-prompt
    pty_output=
    zpty -w -n $current_pty 'print -r -- WSH_AUTO'$'\x03'
    pty_wait_for_prompt cancellation-prompt
    state=$(report_state 2)
    local -a state_fields=("${(@s:|:)state}")
    [[ -z $state_fields[6] && -z $state_fields[17] && $state_fields[18] == reaped ]] || { print -u2 -r -- "asynchronous state survived Ctrl-C: ${(qqq)state}"; exit 1; }
    pty_read_available
    pty_output=
    zpty -w $current_pty '_wsh_test_late_widget() { BUFFER+="LATE"; CURSOR=$#BUFFER }; zle -N _wsh_test_late_widget; bindkey -M emacs "^V" _wsh_test_late_widget; _zsh_autosuggest_bind_widgets; print -r -- WSH_LATE_WIDGET_BOUND'
    pty_wait_for_text WSH_LATE_WIDGET_BOUND late-widget-binding
    pty_wait_for_prompt late-widget-prompt
    zpty -w -n $current_pty A$'\x16\x07'
    wait_for_lines $child_buffer_log 6
    [[ $(sed -n '6p' $child_buffer_log) == ALATE\|* ]] || { print -u2 -r -- "explicit rebind did not incorporate a later widget: ${(qqq)$(sed -n '6p' $child_buffer_log)}"; exit 1; }
  fi
  stop_variant
done

print -r -- 'PASS: autosuggestion display, acceptance, ownership, configuration, composition, custom widgets, and cancellation'
