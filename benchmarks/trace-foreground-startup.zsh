#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 4 )) || {
  print -u2 -- 'usage: trace-foreground-startup.zsh OUTPUT-DIRECTORY MANAGER BUNDLE PROBE-SOURCE'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly bundle=${3:A}
readonly probe_source=${4:A}
readonly scratch=$(mktemp -d /var/tmp/wsh-foreground-trace.XXXXXX)
readonly stage=$(mktemp -d "${output:h}/.${output:t}.XXXXXX")
readonly state_root=$scratch/state
readonly fixture=$scratch/fixture
readonly home=$scratch/home
readonly probe=$scratch/foreground-probe
typeset -g current_pty= current_variant= pty_output=

[[ ! -e $output && ! -L $output && -x $manager && -x $bundle/bin/zsh && -f $probe_source ]] || {
  print -u2 -- 'error: output must be new and manager, bundle, and probe source must exist'
  exit 2
}
(( $+commands[strace] )) || {
  print -u2 -- 'error: strace is required'
  exit 2
}

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $scratch $stage
}
trap cleanup EXIT INT TERM

command gcc -std=c11 -O2 -Wall -Wextra -Werror $probe_source -o $probe
command mkdir -p -- $fixture $home
print -r -- 'typeset -g WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1
typeset -g WSH_DISABLE_AUTOSUGGESTIONS=1
typeset -g WSH_DISABLE_SYNTAX_HIGHLIGHTING=1' >| $home/.zshrc
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh foreground trace'
git -C $fixture config user.email foreground-trace@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial
$manager bundle activate $bundle --state-root $state_root >/dev/null

trace_child() {
  builtin cd -q -- $fixture
  export HOME=$home ZDOTDIR=$bundle/share/wsh/zdotdir WSH_USER_ZDOTDIR=$home
  export WSH_BUNDLE_ROOT=$bundle WSH_RUNTIME=$bundle/bin/wsh-runtime
  export WSH_THEME=$bundle/share/wsh/themes/minimal.toml TERM=xterm-256color
  unset WSH_RUN_FOREGROUND WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  local report=$scratch/${current_variant}.report
  if [[ $current_variant == current ]]; then
    local invocation="${probe} ${report} exit0"
    exec strace -ff -qq -e trace=process -o $stage/current.trace $bundle/bin/zsh -d -l -i -c "${invocation}; exec \"\$0\" -d -l -i" $bundle/bin/zsh
  fi
  exec strace -ff -qq -e trace=process -o $stage/candidate.trace $manager run-foreground --state-root $state_root --login -- $probe $report exit0
}

read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

local variant
for variant in current candidate; do
  current_variant=$variant
  current_pty=wsh_foreground_trace_${variant}_${$}
  pty_output=
  zpty -b $current_pty trace_child
  local -F deadline=$(( EPOCHREALTIME + 8 ))
  while (( EPOCHREALTIME < deadline )); do
    read_available
    [[ $pty_output == *$'WSH_FOREGROUND_READY\t'* && $pty_output == *$'\e]133;B'* ]] && break
    zselect -t 1 2>/dev/null || true
  done
  [[ $pty_output == *$'WSH_FOREGROUND_READY\t'* && $pty_output == *$'\e]133;B'* ]] || {
    print -u2 -r -- "timeout tracing ${variant}: ${(qqq)pty_output}"
    exit 1
  }
  zpty -w $current_pty exit
  zselect -t 20 2>/dev/null || true
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
done

print -r -- $'variant\tcount\texecutable' > $stage/executables.tsv
for variant in current candidate; do
  local record count executable
  while IFS= read -r record; do
    count=${record%% *}
    executable=${record#* }
    executable=${executable:t}
    printf '%s\t%d\t%s\n' $variant $count $executable >> $stage/executables.tsv
  done < <(sed -n 's/.*execve("\([^"]*\)".* = 0$/\1/p' $stage/${variant}.trace.* | sort | uniq -c | sed 's/^[[:space:]]*//')
done

local current_zsh=$(awk -F '\t' '$1 == "current" && $3 == "zsh" {print $2}' $stage/executables.tsv)
local candidate_zsh=$(awk -F '\t' '$1 == "candidate" && $3 == "zsh" {print $2}' $stage/executables.tsv)
[[ $current_zsh == 2 && $candidate_zsh == 1 ]] || {
  print -u2 -- "error: expected two current-wrapper Zsh execs and one candidate Zsh exec"
  exit 1
}

mv -- $stage $output
trap - EXIT INT TERM
command rm -rf -- $scratch
print -r -- $output
