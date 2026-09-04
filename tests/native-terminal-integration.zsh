#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 4 )) || {
  print -u2 -- 'usage: native-terminal-integration.zsh ZSH WAKTERM_INTEGRATION native|duplicate|coexist TRANSCRIPT'
  exit 2
}

readonly zsh_binary=${1:A}
readonly wakterm_integration=${2:A}
readonly variant=$3
readonly transcript=${4:A}
readonly test_root=$(mktemp -d /var/tmp/wsh-native-terminal-integration.XXXXXX)
readonly home=$test_root/home
readonly hook_log=$test_root/hooks.log
readonly pty_name=wsh_native_terminal_${RANDOM}_${$}
typeset -g pty_output=

[[ -x $zsh_binary && ( $variant == native || -r $wakterm_integration ) && ( $variant == native || $variant == duplicate || $variant == coexist ) ]] || {
  print -u2 -- 'error: invalid Zsh binary, Wakterm integration, or variant'
  exit 2
}

cleanup() {
  zpty -d $pty_name 2>/dev/null || true
  command rm -rf -- $test_root
}
trap cleanup EXIT INT TERM

command mkdir -p -- $home ${transcript:h}
print -r -- 'typeset -ga .term.extensions=(-query)' >| $home/.zshenv
print -r -- "PS1='WSH_NATIVE_PROMPT> '
PS2='WSH_NATIVE_CONTINUE> '
typeset -ga precmd_functions preexec_functions
_wsh_native_user_precmd() { print -r -- precmd >> ${(q)hook_log}; }
_wsh_native_user_preexec() { print -r -- preexec >> ${(q)hook_log}; }
precmd_functions+=(_wsh_native_user_precmd)
preexec_functions+=(_wsh_native_user_preexec)" >| $home/.zshrc
if [[ $variant != native ]]; then
  print -r -- "typeset -gx WAKTERM_SHELL_SKIP_USER_VARS=1
source ${(q)wakterm_integration}" >> $home/.zshrc
fi

native_child() {
  export HOME=$home ZDOTDIR=$home TERM=xterm-256color
  unset WAKTERM_SHELL_SKIP_ALL WAKTERM_SHELL_SKIP_SEMANTIC_ZONES WAKTERM_SHELL_SKIP_CWD
  if [[ $variant == coexist ]]; then
    export WSH_NATIVE_TERMINAL_INTEGRATION=1
  else
    unset WSH_NATIVE_TERMINAL_INTEGRATION
  fi
  command stty -echo
  exec $zsh_binary -di
}

read_available() {
  local chunk
  while zpty -r -t $pty_name chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

wait_for_new() {
  local expected=$1 label=$2 previous_count=$3
  local -F deadline=$(( EPOCHREALTIME + 5 ))
  while (( EPOCHREALTIME < deadline )); do
    read_available
    local remainder=${pty_output[$(( previous_count + 1 )),-1]}
    [[ $remainder == *$expected* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -r -- "timeout waiting for ${label}: ${(qqq)pty_output}"
  return 1
}

send_and_wait_prompt() {
  local input=$1 label=$2 before=${#pty_output}
  if [[ -n $input ]]; then
    zpty -w $pty_name $input
  else
    zpty -w -n $pty_name $'\n'
  fi
  wait_for_new $'\e]133;B' $label $before
}

zpty -b $pty_name native_child
wait_for_new $'\e]133;B' initial-prompt 0
send_and_wait_prompt '' empty-input
send_and_wait_prompt ':' successful-command
send_and_wait_prompt 'false' failing-command
send_and_wait_prompt "cd -- ${(q)test_root}" directory-change
send_and_wait_prompt "print -n -- \\$'\\e]7;file://remote.example/tmp\\e\\\\'" child-directory-report
send_and_wait_prompt $'print -r -- \\\nWSH_MULTILINE' multiline-command
send_and_wait_prompt 'print -n -- WSH_NO_NEWLINE' no-newline-command

typeset -i before=${#pty_output}
zpty -w -n $pty_name $'partially-typed\x03'
wait_for_new $'\e]133;B' editing-interrupt $before

zpty -w $pty_name exit
local -F exit_deadline=$(( EPOCHREALTIME + 3 ))
while zpty -t $pty_name 2>/dev/null && (( EPOCHREALTIME < exit_deadline )); do
  read_available
  zselect -t 1 2>/dev/null || true
done
read_available
print -rn -- $pty_output >| $transcript

count_sequence() {
  LC_ALL=C grep -aFo -- $1 $transcript | wc -l
}

typeset -i prompts=$(count_sequence $'\e]133;A')
typeset -i valid_prompts=$(count_sequence $'\e]133;A;cl=m;aid=z')
typeset -i prompt_ends=$(count_sequence $'\e]133;B')
typeset -i command_starts=$(count_sequence $'\e]133;C')
typeset -i command_ends=$(count_sequence $'\e]133;D')
typeset -i cwd_reports=$(count_sequence $'\e]7;file:')
typeset -i local_cwd_reports=$(count_sequence $'\e]7;file://'${HOST})
typeset -i user_precmds=$(grep -c '^precmd$' $hook_log)
typeset -i user_preexecs=$(grep -c '^preexec$' $hook_log)
typeset -i child_cwd_reset=0
[[ $pty_output == *$'\e]7;file://remote.example/tmp\e\\'*$'\e]7;file://'${HOST}*$'\e]133;A'* ]] && child_cwd_reset=1

print -r -- $'variant\tprompt_starts\tvalid_prompt_starts\tprompt_ends\tcommand_starts\tcommand_ends\tcwd_reports\tlocal_cwd_reports\tchild_cwd_reset\tuser_precmds\tuser_preexecs'
print -r -- "${variant}"$'\t'"${prompts}"$'\t'"${valid_prompts}"$'\t'"${prompt_ends}"$'\t'"${command_starts}"$'\t'"${command_ends}"$'\t'"${cwd_reports}"$'\t'"${local_cwd_reports}"$'\t'"${child_cwd_reset}"$'\t'"${user_precmds}"$'\t'"${user_preexecs}"

if [[ ${WSH_EXPECT_NATIVE_TERMINAL_PASS:-0} == 1 ]]; then
  [[ $prompts == 10 && $valid_prompts == $prompts && $prompt_ends == $prompts ]]
  [[ $command_starts == 7 && $command_ends == 6 ]]
  [[ $local_cwd_reports == 10 && $child_cwd_reset == 1 ]]
  [[ $user_precmds == 9 && $user_preexecs == 7 ]]
fi
