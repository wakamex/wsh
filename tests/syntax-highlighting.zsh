#!/usr/bin/env zsh

export WSH_THEME=minimal

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 1 )) || {
  print -u2 -- 'usage: syntax-highlighting.zsh BUNDLE'
  exit 2
}


readonly bundle=${1:A}
readonly test_root=$(mktemp -d /var/tmp/wsh-syntax-correctness.XXXXXX)
readonly state_root=$test_root/state
readonly fixture=$test_root/fixture
readonly exact_source=$test_root/exact
readonly older_source=$test_root/older
readonly older_modified_source=$test_root/older-modified
readonly modified_source=$test_root/modified
readonly custom_source=$test_root/custom
typeset -g current_pty= pty_output= child_home= child_buffer_log= child_state_log=

[[ -x $bundle/bin/wsh && -x $bundle/bin/zsh && -f $bundle/share/wsh/defaults/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]] || {
  print -u2 -- 'error: manager or bundle is invalid'
  exit 2
}

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $test_root
}
trap cleanup EXIT INT TERM

command mkdir -p -- $state_root $fixture
command cp -R -- $bundle/share/wsh/defaults/zsh-syntax-highlighting $exact_source
if [[ -f $exact_source/highlighters/main/known-main-highlighter.zsh ]]; then
  command cp -- $exact_source/highlighters/main/known-main-highlighter.zsh $exact_source/highlighters/main/main-highlighter.zsh
  command rm -f -- $exact_source/highlighters/main/main-highlighter.zsh.zwc
fi
command cp -R -- $exact_source $older_source
command cp -- $exact_source/recognized/b2c910a/zsh-syntax-highlighting.zsh $older_source/zsh-syntax-highlighting.zsh
command cp -- $exact_source/recognized/b2c910a/main-highlighter.zsh $older_source/highlighters/main/main-highlighter.zsh
command rm -f -- $older_source/zsh-syntax-highlighting.zsh.zwc $older_source/highlighters/main/main-highlighter.zsh.zwc
print -r -- 0.8.0-alpha2-dev >| $older_source/.version
command cp -R -- $older_source $older_modified_source
print -r -- '# user main change' >> $older_modified_source/highlighters/main/main-highlighter.zsh
command cp -R -- $exact_source $modified_source
command cp -R -- $exact_source $custom_source
print -r -- '# wsh modified fixture' >> $modified_source/highlighters/main/main-highlighter.zsh
command mkdir -p -- $custom_source/highlighters/custom
print -r -- '_zsh_highlight_highlighter_custom_predicate() { return 0 }
_zsh_highlight_highlighter_custom_paint() { _zsh_highlight_add_highlight 0 $#BUFFER custom }' >| $custom_source/highlighters/custom/custom-highlighter.zsh

python3 "${0:A:h:h}/build/native_manifest.py" verify $bundle >/dev/null
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh syntax highlighting correctness test'
git -C $fixture config user.email syntax-correctness@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial

write_home() {
  local variant=$1
  local home=$test_root/home-$variant
  command mkdir -p -- $home
  local config=$home/.zshrc
  print -r -- 'typeset -gA ZSH_HIGHLIGHT_STYLES
ZSH_HIGHLIGHT_STYLES[arg0]=fg=blue
ZSH_HIGHLIGHT_STYLES[unknown-token]=fg=red
ZSH_HIGHLIGHT_STYLES[double-quoted-argument]=fg=yellow
ZSH_HIGHLIGHT_STYLES[path]=underline
print -s "print \"WSH_SYNTAX_COMPLETE\""' >| $config

  case $variant in
    external)
      print -r -- "source ${(q)exact_source}/zsh-syntax-highlighting.zsh" >> $config
      ;;
    older|older-ready)
      [[ $variant != older-ready ]] || print -r -- 'zmodload zsh/zle' >> $config
      print -r -- "source ${(q)older_source}/zsh-syntax-highlighting.zsh" >> $config
      ;;
    older-modified)
      print -r -- "zmodload zsh/zle
source ${(q)older_modified_source}/zsh-syntax-highlighting.zsh" >> $config
      ;;
    disabled-external)
      print -r -- "zmodload zsh/zle
WSH_DISABLE_SYNTAX_HIGHLIGHTING=1
source ${(q)older_source}/zsh-syntax-highlighting.zsh" >> $config
      ;;
    override)
      print -r -- "zmodload zsh/zle
source ${(q)exact_source}/zsh-syntax-highlighting.zsh
_zsh_highlight_main__is_redirection() { return 1 }" >> $config
      ;;
    external-ready)
      print -r -- "zmodload zsh/zle
source ${(q)exact_source}/zsh-syntax-highlighting.zsh" >> $config
      ;;
    modified-inactive)
      print -r -- "source ${(q)modified_source}/zsh-syntax-highlighting.zsh" >> $config
      ;;
    modified-ready)
      print -r -- "zmodload zsh/zle
source ${(q)modified_source}/zsh-syntax-highlighting.zsh" >> $config
      ;;
    custom-ready)
      print -r -- "typeset -ga ZSH_HIGHLIGHT_HIGHLIGHTERS=(main custom)
typeset -g ZSH_HIGHLIGHT_HIGHLIGHTERS_DIR=${(q)custom_source}/highlighters
typeset -g ZSH_HIGHLIGHT_STYLES[custom]=bold
zmodload zsh/zle
source ${(q)custom_source}/zsh-syntax-highlighting.zsh" >> $config
      ;;
    disabled)
      print -r -- 'typeset -g WSH_DISABLE_SYNTAX_HIGHLIGHTING=1' >> $config
      ;;
    configured)
      print -r -- 'typeset -ga ZSH_HIGHLIGHT_HIGHLIGHTERS=(main brackets)
typeset -g ZSH_HIGHLIGHT_STYLES[bracket-level-1]=fg=magenta' >> $config
      ;;
    clean|composition) ;;
  esac

  [[ $variant == composition ]] || print -r -- 'typeset -g WSH_DISABLE_AUTOSUGGESTIONS=1' >> $config
  print -r -- 'autoload -Uz add-zle-hook-widget
typeset -gi WSH_TEST_CUSTOM_REDRAWS=0
_wsh_test_custom_redraw() { (( ++WSH_TEST_CUSTOM_REDRAWS )) }
_wsh_test_report_buffer() {
  print -r -- "$BUFFER|$POSTDISPLAY|${(j:,:)region_highlight}" >> $WSH_TEST_BUFFER_LOG
  BUFFER=""
  POSTDISPLAY=""
  region_highlight=()
  zle .accept-line
}
_wsh_test_report_state() {
  zmodload zsh/parameter
  local -a redraw_hooks=() finish_hooks=()
  zstyle -a zle-line-pre-redraw widgets redraw_hooks
  zstyle -a zle-line-finish widgets finish_hooks
  local -a syntax_redraw_hooks=(${(M)redraw_hooks:#*:_zsh_highlight__zle-line-pre-redraw})
  local -a syntax_finish_hooks=(${(M)finish_hooks:#*:_zsh_highlight__zle-line-finish})
  local -a custom_redraw_hooks=(${(M)redraw_hooks:#*:_wsh_test_custom_redraw})
  local -a syntax_preexec_hooks=(${(M)preexec_functions:#_zsh_highlight_preexec_hook})
  local native_main=0
  [[ ${functions[_zsh_highlight_highlighter_main_paint]:-} == *wsh-highlight-main* ]] && native_main=1
  local source=none
  (( ${+ZSH_HIGHLIGHT_VERSION} )) && source=$functions_source[_zsh_highlight]
  print -r -- "${WSH_SYNTAX_HIGHLIGHTING_OWNER-unset}|${ZSH_HIGHLIGHT_VERSION-unset}|${source}|${#syntax_redraw_hooks}|${#syntax_finish_hooks}|${#syntax_preexec_hooks}|${#custom_redraw_hooks}|${(j:,:)ZSH_HIGHLIGHT_HIGHLIGHTERS}|${ZSH_HIGHLIGHT_STYLES[arg0]-unset}|${ZSH_HIGHLIGHT_STYLES[unknown-token]-unset}|${ZSH_HIGHLIGHT_STYLES[bracket-level-1]-unset}|${WSH_TEST_CUSTOM_REDRAWS}|${POSTDISPLAY}|${(j:,:)region_highlight}|native_main=$native_main|legacy_parser=${+functions[_zsh_highlight_main_highlighter_highlight_list]}" >> $WSH_TEST_STATE_LOG
}
zle -N _wsh_test_report_buffer
zle -N _wsh_test_report_state
bindkey -M emacs "^G" _wsh_test_report_buffer
bindkey -M emacs "^T" _wsh_test_report_state
add-zle-hook-widget zle-line-pre-redraw _wsh_test_custom_redraw' >> $config
}

pty_read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

pty_wait_for() {
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
  export WSH_TEST_BUFFER_LOG=$child_buffer_log
  export WSH_TEST_STATE_LOG=$child_state_log
  export TERM=xterm-256color
  unset EDITOR VISUAL WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  exec $bundle/bin/wsh -d
}

start_variant() {
  local variant=$1
  child_home=$test_root/home-$variant
  child_buffer_log=$test_root/$variant-buffer.log
  child_state_log=$test_root/$variant-state.log
  : >| $child_buffer_log
  : >| $child_state_log
  current_pty=wsh_syntax_${variant//[^A-Za-z0-9]/_}_${$}
  pty_output=
  zpty -b $current_pty managed_child
  pty_wait_for git:main startup-prompt
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

report_buffer() {
  local input=$1 line_number=$2
  zpty -w -n $current_pty $input
  zselect -t 2 2>/dev/null || true
  zpty -w -n $current_pty $'\x07'
  wait_for_lines $child_buffer_log $line_number
  sed -n "${line_number}p" $child_buffer_log
}

local -a variants=(clean external external-ready older older-ready older-modified disabled-external override modified-inactive modified-ready custom-ready disabled configured composition)
local variant state buffer_state
for variant in $variants; do
  write_home $variant
  start_variant $variant
  [[ $pty_output != *'no such file or directory'* ]] || { print -u2 -r -- "runtime file was missing for ${variant}: ${(qqq)pty_output}"; exit 1; }
  state=$(report_state)
  case $variant in
    clean|configured|composition)
      if [[ -f $bundle/share/wsh/defaults/zsh-syntax-highlighting/highlighters/main/known-main-highlighter.zsh ]]; then
        [[ $state == *'|native_main=1|legacy_parser=0' ]] || { print -u2 -r -- "native main ownership missing for ${variant}: $state"; exit 1; }
      fi
      [[ $state == wsh\|0.8.1-dev\|${bundle}/share/wsh/defaults/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh\|1\|1\|1\|1\|* ]] || { print -u2 -r -- "unexpected bundled state for ${variant}: $state"; exit 1; }
      ;;
    older|older-ready)
      [[ $state == external-exact\|0.8.0-alpha2-dev\|${older_source}/zsh-syntax-highlighting.zsh\|1\|1\|1\|1\|* && $state == *'|native_main=1|'* ]] || { print -u2 -r -- "older upstream handoff failed: $state"; exit 1; }
      ;;
    older-modified)
      [[ $state == external-unknown\|* && $state == *'|native_main=0|'* ]] || { print -u2 -- "modified older copy replaced: $state"; exit 1; }
      ;;
    disabled-external)
      [[ $state == disabled\|* && $state == *'|native_main=0|'* ]] || { print -u2 -- "disabled external copy replaced: $state"; exit 1; }
      ;;
    override)
      [[ $state == external-unknown\|* && $state == *'|native_main=0|'* ]] || { print -u2 -r -- "runtime override was not preserved: $state"; exit 1; }
      ;;
    external|external-ready)
      [[ $state == *'|native_main=1|'* ]] || { print -u2 -r -- "native external handoff missing: $state"; exit 1; }
      [[ $state == external-exact\|0.8.1-dev\|${exact_source}/zsh-syntax-highlighting.zsh\|1\|1\|1\|1\|* ]] || { print -u2 -r -- "unexpected exact external state for ${variant}: $state"; exit 1; }
      ;;
    modified-inactive)
      [[ $state == external-unknown\|0.8.1-dev\|${modified_source}/zsh-syntax-highlighting.zsh\|0\|0\|1\|1\|* ]] || { print -u2 -r -- "modified inactive implementation was not preserved: $state"; exit 1; }
      ;;
    modified-ready)
      [[ $state == external-unknown\|0.8.1-dev\|${modified_source}/zsh-syntax-highlighting.zsh\|1\|1\|1\|1\|* ]] || { print -u2 -r -- "modified active implementation was not preserved: $state"; exit 1; }
      ;;
    custom-ready)
      [[ $state == *'|native_main=1|'* ]] || { print -u2 -- "custom composition lost native main: $state"; exit 1; }
      [[ $state == external-unknown\|0.8.1-dev\|${custom_source}/zsh-syntax-highlighting.zsh\|1\|1\|1\|1\|main,custom\|* ]] || { print -u2 -r -- "custom highlighter was not preserved: $state"; exit 1; }
      ;;
    disabled)
      [[ $state == disabled\|unset\|none\|0\|0\|0\|1\|* ]] || { print -u2 -r -- "unexpected disabled state: $state"; exit 1; }
      ;;
  esac

  if [[ $variant == configured ]]; then
    [[ $state == *'|main,brackets|fg=blue|fg=red|fg=magenta|'* ]] || { print -u2 -r -- "configuration was not preserved: $state"; exit 1; }
  fi
  if [[ $variant != disabled && $variant != modified-inactive ]]; then
    buffer_state=$(report_buffer 'print "WSH_SYNTAX"' 1)
    [[ $buffer_state == 'print "WSH_SYNTAX"|'*fg=blue*fg=yellow* ]] || { print -u2 -r -- "valid command was not highlighted for ${variant}: $buffer_state"; exit 1; }
    buffer_state=$(report_buffer wsh_definitely_missing 2)
    [[ $buffer_state == wsh_definitely_missing\|*fg=red* ]] || { print -u2 -r -- "unknown command was not highlighted for ${variant}: $buffer_state"; exit 1; }
    buffer_state=$(report_buffer 'print ./tracked' 3)
    [[ $buffer_state == 'print ./tracked|'*underline* ]] || { print -u2 -r -- "path was not highlighted for ${variant}: $buffer_state"; exit 1; }
  fi
  if [[ $variant == custom-ready ]]; then
    [[ $buffer_state == *bold* ]] || { print -u2 -r -- "custom highlighter did not run: $buffer_state"; exit 1; }
  fi
  if [[ $variant == composition ]]; then
    pty_output=
    zpty -w -n $current_pty 'print "WSH_SYN'
    pty_wait_for TAX_COMPLETE autosuggestion
    zpty -w -n $current_pty $'\x07'
    wait_for_lines $child_buffer_log 4
    buffer_state=$(sed -n '4p' $child_buffer_log)
    [[ $buffer_state == 'print "WSH_SYN|TAX_COMPLETE"|'*memo=zsh-syntax-highlighting* ]] || { print -u2 -r -- "autosuggestions did not compose with syntax highlighting: $buffer_state"; exit 1; }
  fi
  stop_variant
done

print -r -- 'PASS: syntax highlighting ownership, semantics, configuration, hooks, and editing-default composition'
