#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 4 )) || {
  print -u2 -- 'usage: trace-history-substring-search-processes.zsh OUTPUT MANAGER BUNDLE HSS-REPOSITORY'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly bundle=${3:A}
readonly hss_repository=${4:A}
readonly hss_revision=14c8d2e0ffaee98f2df9850b19944f32546fdea5
[[ ! -e $output && ! -L $output && -x $manager && -x $bundle/bin/zsh ]] || {
  print -u2 -- 'error: output must be new and manager and bundle must exist'
  exit 2
}
git -C $hss_repository cat-file -e ${hss_revision}^{commit} 2>/dev/null || {
  print -u2 -- "error: plugin revision is unavailable: $hss_revision"
  exit 2
}

readonly trace_root=$(mktemp -d /var/tmp/wsh-history-processes.XXXXXX)
readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
readonly state_root=$trace_root/state
readonly fixture=$trace_root/fixture
readonly hss_source=$trace_root/hss
typeset -g current_pty= pty_output= current_variant= child_home= child_marker=
typeset -gA search_started=()
typeset -gA search_ended=()

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $trace_root $stage
}
trap cleanup EXIT INT TERM

command mkdir -p -- $state_root $fixture $hss_source
git -C $hss_repository archive $hss_revision | tar -xf - -C $hss_source
$manager bundle activate $bundle --state-root $state_root >/dev/null
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh history process trace'
git -C $fixture config user.email history-processes@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial

local variant home
for variant in clean external; do
  home=$trace_root/home-$variant
  command mkdir -p -- $home
  print -r -- 'print -s "print -r -- WSH_MATCH"
_wsh_trace_report() {
  print -r -- done >> $WSH_TRACE_MARKER
}
zle -N _wsh_trace_report
bindkey -M emacs '^G' _wsh_trace_report' >| $home/.zshrc
  if [[ $variant == external ]]; then
    print -r -- "source ${(q)hss_source}/zsh-history-substring-search.zsh
bindkey -M emacs \$'\\eOA' history-substring-search-up
bindkey -M emacs \$'\\eOB' history-substring-search-down" >> $home/.zshrc
  fi
done

pty_read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

pty_wait_for_prompt() {
  local -F deadline=$(( EPOCHREALTIME + 5 ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    [[ $pty_output == *'% '* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -r -- "timeout waiting for prompt: ${(qqq)pty_output}"
  return 1
}

trace_child() {
  builtin cd -q -- $fixture
  export HOME=$child_home
  export ZDOTDIR=$child_home
  export WSH_STATE_ROOT=$state_root
  export WSH_TRACE_MARKER=$child_marker
  export TERM=xterm-256color
  unset EDITOR VISUAL WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  exec strace -ff -qq -ttt -e trace=process -o $trace_root/$current_variant.trace $manager run --state-root $state_root
}

for variant in clean external; do
  current_variant=$variant
  child_home=$trace_root/home-$variant
  child_marker=$trace_root/$variant.marker
  : >| $child_marker
  current_pty=wsh_history_trace_${variant}_${$}
  pty_output=
  zpty -b $current_pty trace_child
  pty_wait_for_prompt
  search_started[$variant]=$EPOCHREALTIME
  pty_output=
  zpty -w -n $current_pty wsh_match
  zpty -w -n $current_pty $'\eOA\x07'
  local -F deadline=$(( EPOCHREALTIME + 3 ))
  while (( EPOCHREALTIME < deadline )) && [[ ! -s $child_marker ]]; do
    zselect -t 1 2>/dev/null || true
  done
  [[ -s $child_marker ]] || {
    print -u2 -r -- "search interaction did not complete for ${variant}: ${(qqq)pty_output}"
    exit 1
  }
  search_ended[$variant]=$EPOCHREALTIME
  zpty -w -n $current_pty $'\x03'
  zpty -w $current_pty exit
  zselect -t 20 2>/dev/null || true
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
done

print -r -- $'variant\tphase\tcount\texecutable' > $stage
for variant in clean external; do
  local count executable phase
  while read -r count phase executable; do
    executable=${executable:t}
    printf '%s\t%s\t%d\t%s\n' $variant $phase $count $executable >> $stage
  done < <(awk -v start=${search_started[$variant]} -v finish=${search_ended[$variant]} '
    /execve\("/ && / = 0$/ {
      phase = ($1 < start ? "startup" : ($1 <= finish ? "search" : "cleanup"))
      line = $0
      sub(/^[^ ]+ execve\("/, "", line)
      sub(/".*/, "", line)
      print phase "\t" line
    }
  ' $trace_root/$variant.trace.* | sort -k1,1 -k2,2 | uniq -c)
done

[[ $(awk -F '\t' 'NR > 1 && $2 == "search" {sum += $3} END {print sum + 0}' $stage) == 0 ]] || {
  command cat -- $stage >&2
  print -u2 -- 'error: history search started an external process'
  exit 1
}
[[ $(awk -F '\t' 'NR > 1 && ($4 == "sha256sum" || $4 == "cmp") {sum += $3} END {print sum + 0}' $stage) == 0 ]] || {
  print -u2 -- 'error: compatibility recognition started an external comparison process'
  exit 1
}

mv -- $stage $output
trap - EXIT INT TERM
command rm -rf -- $trace_root
print -r -- $output
