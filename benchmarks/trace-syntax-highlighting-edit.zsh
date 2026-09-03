#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 5 )) || {
  print -u2 -- 'usage: trace-syntax-highlighting-edit.zsh OUTPUT-DIRECTORY MANAGER BUNDLE SYNTAX-REPOSITORY CPU'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly bundle=${3:A}
readonly plugin_repository=${4:A}
readonly cpu=$5
readonly plugin_revision=2fc57d63067c18b1100ecdbf684fa5baf49459d1
[[ ! -e $output && ! -L $output && -x $manager && -x $bundle/bin/zsh ]] || {
  print -u2 -- 'error: output must be new and manager or bundle is invalid'
  exit 2
}
git -C $plugin_repository cat-file -e ${plugin_revision}^{commit} 2>/dev/null || exit 2
(( $+commands[strace] )) || { print -u2 -- 'error: strace is required'; exit 2; }

readonly trace_root=$(mktemp -d /var/tmp/wsh-syntax-trace.XXXXXX)
readonly stage=$(mktemp -d "${output:h}/.${output:t}.XXXXXX")
readonly state_root=$trace_root/state
readonly fixture=$trace_root/fixture
readonly home=$trace_root/home
readonly plugin=$trace_root/plugin
readonly owner_log=$trace_root/owner.log
typeset -g pty_name=wsh_syntax_trace_${$} pty_output=

cleanup() {
  zpty -d $pty_name 2>/dev/null || true
  command rm -rf -- $trace_root $stage
}
trap cleanup EXIT INT TERM

command mkdir -p -- $state_root $fixture $home $plugin
git -C $plugin_repository archive $plugin_revision | tar -xf - -C $plugin
$manager bundle activate $bundle --state-root $state_root >/dev/null
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh syntax highlighting process trace'
git -C $fixture config user.email syntax-trace@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial
print -r -- "typeset -g WSH_DISABLE_AUTOSUGGESTIONS=1
source ${(q)plugin}/zsh-syntax-highlighting.zsh
_wsh_trace_report_owner() {
  local -a hooks=()
  zstyle -a zle-line-pre-redraw widgets hooks
  local -a matches=(\${(M)hooks:#*:_zsh_highlight__zle-line-pre-redraw})
  print -r -- \"\${WSH_SYNTAX_HIGHLIGHTING_OWNER-unset}|\${#matches}\" >| \$WSH_TRACE_OWNER_LOG
}
_wsh_trace_set_buffer() { BUFFER=\"print \\\"WSH_HIGHLIGHT_END\\\"\"; CURSOR=\$#BUFFER }
zle -N _wsh_trace_report_owner
zle -N _wsh_trace_set_buffer
bindkey -M emacs \"^T\" _wsh_trace_report_owner
bindkey -M emacs \"^Xs\" _wsh_trace_set_buffer" >| $home/.zshrc

pty_read_available() {
  local chunk
  while zpty -r -t $pty_name chunk 2>/dev/null; do pty_output+=$chunk; done
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

trace_child() {
  builtin cd -q -- $fixture
  export HOME=$home ZDOTDIR=$home WSH_STATE_ROOT=$state_root WSH_TRACE_OWNER_LOG=$owner_log TERM=xterm-256color
  unset EDITOR VISUAL WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  exec strace -ff -ttt -o $stage/process.trace -e trace=process taskset -c $cpu $manager run --state-root $state_root
}

zpty -b $pty_name trace_child
pty_wait_for git:main prompt
zpty -w -n $pty_name $'\x14'
local -F owner_deadline=$(( EPOCHREALTIME + 3 ))
while [[ ! -s $owner_log ]] && (( EPOCHREALTIME < owner_deadline )); do zselect -t 1 2>/dev/null || true; done
[[ $(<$owner_log) == 'external-exact|1' ]] || { print -u2 -r -- "unexpected owner: ${(qqq)$(<$owner_log)}"; exit 1; }
zselect -t 2 2>/dev/null || true
pty_read_available
pty_output=
local -F edit_started=$EPOCHREALTIME edit_finished elapsed_ms
zpty -w -n $pty_name $'\x18s'
pty_wait_for WSH_HIGHLIGHT_END highlighted-buffer
edit_finished=$EPOCHREALTIME
elapsed_ms=$(( (edit_finished - edit_started) * 1000 ))
zpty -w -n $pty_name $'\x03'
pty_output=
pty_wait_for git:main cancellation-prompt
zpty -w $pty_name exit
zpty -d $pty_name 2>/dev/null || true

awk -v start=$edit_started -v finish=$edit_finished '$1 + 0 >= start && $1 + 0 <= finish' $stage/process.trace.* >| $stage/edit-window.trace
readonly processes=$(awk '/ (clone|clone3|fork|vfork)\(/ { ++count } END { print count + 0 }' $stage/edit-window.trace)
readonly execs=$(awk '/ execve\(/ { ++count } END { print count + 0 }' $stage/edit-window.trace)
{
  print -r -- $'count\texecutable'
  awk '/execve\("[^"]+"/ && /= 0$/ { executable=$0; sub(/^.*execve\("/, "", executable); sub(/".*$/, "", executable); sub(/^.*\//, "", executable); print executable }' $stage/process.trace.* | sort | uniq -c | awk '{ print $1 "\t" $2 }'
} >| $stage/executables.tsv
{
  print -r -- "bundle=${bundle:t}"
  print -r -- "plugin_revision=${plugin_revision}"
  print -r -- "owner=$(<$owner_log)"
  print -r -- "cpu=${cpu}"
  printf 'edit_started_epoch=%.9f\n' $edit_started
  printf 'highlight_visible_epoch=%.9f\n' $edit_finished
  printf 'highlight_redraw_ms=%.6f\n' $elapsed_ms
  print -r -- "edit_window_process_creations=${processes}"
  print -r -- "edit_window_execve=${execs}"
} >| $stage/metadata.txt
(( processes == 0 && execs == 0 )) || { print -u2 -- "error: syntax edit created ${processes} processes and ${execs} execs"; exit 1; }
command rm -f -- $stage/process.trace.*
mv -- $stage $output
trap - EXIT INT TERM
command rm -rf -- $trace_root
print -r -- $output
