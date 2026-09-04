#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect

local root=${0:A:h:h}
local zsh_binary=${WSH_TEST_ZSH:-$root/build/out/zsh-cad0d67c-wsh1/bin/zsh}
local zsh_version=$($zsh_binary -fc 'print -r -- $ZSH_VERSION')
local runtime=${WSH_TEST_RUNTIME:-$root/target/release/wsh-runtime}
local integration=${WSH_TEST_INTEGRATION:-$root/integration/integration.zsh}
local theme=${WSH_TEST_THEME:-$root/benchmarks/wsh-benchmark.toml}
local prompt_marker=${WSH_TEST_PROMPT_MARKER:-ZTB_PROMPT>}
local bundle_root=${WSH_TEST_BUNDLE_ROOT:-}
local scratch
scratch=$(mktemp -d /var/tmp/wsh-runtime-pty.XXXXXX)
local pty_name=wsh_runtime_pty
local runtime_pid=-1

cleanup() {
  zpty -d $pty_name 2>/dev/null || true
  if (( runtime_pid > 0 )) && kill -0 $runtime_pid 2>/dev/null; then
    kill -KILL $runtime_pid 2>/dev/null || true
  fi
  command rm -rf -- $scratch
}
trap cleanup EXIT INT TERM

[[ -x $zsh_binary && -x $runtime && -r $integration && -r $theme ]] || {
  print -u2 -- 'runtime PTY test requires the bundled Zsh and release runtime'
  return 1
}

local fixture=$scratch/fixture
command git init -q -b main $fixture
command git -C $fixture config user.name 'wsh test'
command git -C $fixture config user.email test@wsh.invalid
print -r -- seed > $fixture/tracked
command git -C $fixture add tracked
command git -C $fixture commit -qm initial

typeset -g pty_output=''

pty_read_available() {
  local chunk
  while zpty -r -t $pty_name chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

pty_wait_for() {
  local expected=$1
  local -F deadline=$(( EPOCHREALTIME + ${2:-3} ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    [[ $pty_output == *$expected* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  pty_read_available
  print -u2 -r -- "timeout waiting for ${(qqq)expected}: ${(qqq)pty_output}"
  return 1
}

wsh_pty_child() {
  builtin cd -q -- $fixture
  export ZDOTDIR=$scratch/zdotdir
  export PS1='WSH_BOOT> '
  export TERM=xterm-256color
  command mkdir -p $ZDOTDIR
  command stty -echo
  exec $zsh_binary -dfi
}

zpty -b $pty_name wsh_pty_child
pty_wait_for WSH_BOOT 5
local bundle_setup=
if [[ -n $bundle_root ]]; then
  bundle_setup="typeset -gx WSH_BUNDLE_ROOT=${(q)bundle_root}; module_path=(${(q)bundle_root}/lib/zsh/${(q)zsh_version}); fpath=(${(q)bundle_root}/share/zsh/${(q)zsh_version}/functions \$fpath); "
fi
zpty -w $pty_name "${bundle_setup}typeset -gx WSH_RUNTIME=${(q)runtime} WSH_THEME=${(q)theme}; source ${(q)integration}; print -r -- \$'WSH_\\x53ETUP_DONE'"
pty_wait_for WSH_SETUP_DONE 3
pty_wait_for $prompt_marker 3
[[ $pty_output != *'['<->'] '<->* ]] || {
  print -u2 -r -- "runtime startup exposed an internal job announcement: ${(qqq)pty_output}"
  return 1
}
zpty -w $pty_name "print -r -- \$'WSH_\\x4dONITOR='\$options[monitor]"
pty_wait_for WSH_MONITOR= 3
[[ $pty_output == *'WSH_MONITOR=on'* ]] || {
  print -u2 -r -- "runtime startup did not restore interactive job control: ${(qqq)pty_output}"
  return 1
}
zpty -w $pty_name "print -r -- \$'WSH_\\x53HELL_PID='\$\$"
pty_wait_for WSH_SHELL_PID= 3
local shell_pid=${pty_output##*WSH_SHELL_PID=}
shell_pid=${shell_pid%%[^0-9]*}
zpty -w $pty_name "print -r -- \$'WSH_\\x53TATE='\${WSH_RUNTIME_PID}:\${WSH_RUNTIME_READY}:\${WSH_RUNTIME_REPAINTS}"
pty_wait_for WSH_STATE= 3
local state=${pty_output##*WSH_STATE=}
state=${state%%[^0-9:]*}
runtime_pid=${state%%:*}
[[ $state == <1->:1:<1-> ]] || {
  print -u2 -r -- "unexpected live state: ${(qqq)state} output=${(qqq)pty_output}"
  return 1
}
local initial_repaints=${state##*:}
local shell_stat runtime_stat
local -a shell_fields runtime_fields
shell_stat=$(< /proc/${shell_pid}/stat)
runtime_stat=$(< /proc/${runtime_pid}/stat)
shell_fields=(${=shell_stat})
runtime_fields=(${=runtime_stat})
[[ $shell_fields[5] == $shell_pid && $runtime_fields[5] == $runtime_pid && $runtime_fields[5] != $shell_fields[5] ]] || {
  print -u2 -- "runtime shares the interactive shell process group: shell=${shell_pid}:${shell_fields[5]} runtime=${runtime_pid}:${runtime_fields[5]}"
  return 1
}

local hex_payload='' hex_byte
local -i hex_value
for (( hex_value = 1; hex_value <= 255; ++hex_value )); do
  printf -v hex_byte '%02x' $hex_value
  hex_payload+=$hex_byte
done
pty_output=''
zpty -w $pty_name "_wsh_hex_decode ${(q)hex_payload}; _wsh_hex_encode \"\$REPLY\"; print -r -- $'WSH_\\x48EX_ROUNDTRIP='\$REPLY"
pty_wait_for WSH_HEX_ROUNDTRIP= 3
[[ $pty_output == *"WSH_HEX_ROUNDTRIP=${hex_payload}"* ]] || {
  print -u2 -r -- "hex decoder did not preserve byte values: ${(qqq)pty_output}"
  return 1
}

pty_output=''
zpty -w $pty_name ':'
pty_wait_for $prompt_marker 3
local -F unchanged_deadline=$(( EPOCHREALTIME + 0.2 ))
while (( EPOCHREALTIME < unchanged_deadline )); do
  zselect -t 1 2>/dev/null || true
  pty_read_available
done
zpty -w $pty_name "print -r -- \$'WSH_\\x55NCHANGED_REPAINTS='\$WSH_RUNTIME_REPAINTS"
pty_wait_for WSH_UNCHANGED_REPAINTS= 3
local unchanged_repaints=${pty_output##*WSH_UNCHANGED_REPAINTS=}
unchanged_repaints=${unchanged_repaints%%[^0-9]*}
[[ $unchanged_repaints == $initial_repaints ]] || {
  print -u2 -r -- "unchanged prompt repainted: before=$initial_repaints after=$unchanged_repaints output=${(qqq)pty_output}"
  return 1
}

pty_output=''
zpty -w $pty_name $'\x03'
pty_wait_for $prompt_marker 3
kill -0 $runtime_pid 2>/dev/null || {
  print -u2 -- "runtime did not survive Ctrl-C at the prompt: $runtime_pid"
  return 1
}

pty_output=''
zpty -w $pty_name "kill -KILL \$WSH_RUNTIME_PID; print -r -- \$'WSH_\\x43RASH_SENT'"
pty_wait_for WSH_CRASH_SENT 3
zpty -w $pty_name "print -r -- \$'WSH_\\x41FTER_CRASH='\$WSH_RUNTIME_READY; print -r -- \$'WSH_\\x45DITOR_ALIVE'"
pty_wait_for WSH_EDITOR_ALIVE 3
[[ $pty_output == *'WSH_AFTER_CRASH=0'* ]] || {
  print -u2 -r -- "runtime crash did not disable integration: ${(qqq)pty_output}"
  return 1
}
kill -0 $runtime_pid 2>/dev/null && {
  print -u2 -- "crashed runtime survived: $runtime_pid"
  return 1
}
runtime_pid=-1
zpty -w $pty_name exit
zpty -d $pty_name

pty_output=''
zpty -b $pty_name wsh_pty_child
pty_wait_for WSH_BOOT 5
local pid_file=$scratch/runtime.pid
zpty -w $pty_name "typeset -gx WSH_RUNTIME=${(q)runtime} WSH_THEME=${(q)theme}; source ${(q)integration}; print -r -- \$WSH_RUNTIME_PID > ${(q)pid_file}; print -r -- \$'WSH_\\x45XIT_SETUP'"
pty_wait_for WSH_EXIT_SETUP 3
runtime_pid=$(< $pid_file)
zpty -w $pty_name exit
local -F exit_deadline=$(( EPOCHREALTIME + 3 ))
while kill -0 $runtime_pid 2>/dev/null && (( EPOCHREALTIME < exit_deadline )); do
  zselect -t 1 2>/dev/null || true
done
kill -0 $runtime_pid 2>/dev/null && {
  print -u2 -- "runtime survived normal shell exit: $runtime_pid"
  return 1
}
runtime_pid=-1
zpty -d $pty_name 2>/dev/null || true
print -r -- 'PASS: hidden isolated internal job, restored job control, prompt interrupt survival, unchanged repaint suppression, runtime crash fallback, and shell-exit cleanup'
