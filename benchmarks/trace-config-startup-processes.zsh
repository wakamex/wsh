#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 3 )) || {
  print -u2 -- 'usage: trace-config-startup-processes.zsh OUTPUT MANAGER BUNDLE'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly bundle=${3:A}
[[ ! -e $output && ! -L $output && -x $manager && -x $bundle/bin/zsh ]] || {
  print -u2 -- 'error: output must be new and manager and bundle must exist'
  exit 2
}

readonly scratch=$(mktemp -d /var/tmp/wsh-config-processes.XXXXXX)
readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
readonly state_root=$scratch/state
readonly fixture=$scratch/fixture
readonly user_zdotdir=$scratch/user-zdotdir
readonly direct_zdotdir=$scratch/direct-zdotdir
typeset -g current_pty= current_variant= pty_output=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $scratch $stage
}
trap cleanup EXIT INT TERM

command mkdir -p -- $state_root $fixture $user_zdotdir $direct_zdotdir
$manager bundle activate $bundle --state-root $state_root >/dev/null
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh startup process trace'
git -C $fixture config user.email processes@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial
print -r -- "alias wsh_config_probe='print -r -- WSH_CONFIG_ALIAS_OK'" > $user_zdotdir/.zshrc
print -r -- "module_path=(${(q)bundle}/lib/zsh/5.9.2)
fpath=(${(q)bundle}/share/zsh/5.9.2/functions \$fpath)
source ${(q)user_zdotdir}/.zshrc
source ${(q)bundle}/share/wsh/integration.zsh" > $direct_zdotdir/.zshrc

trace_child() {
  builtin cd -q -- $fixture
  export HOME=$user_zdotdir
  export TERM=xterm-256color
  command stty -echo
  if [[ $current_variant == direct ]]; then
    export ZDOTDIR=$direct_zdotdir
    export WSH_BUNDLE_ROOT=$bundle
    export WSH_RUNTIME=$bundle/bin/wsh-runtime
    export WSH_THEME=$bundle/share/wsh/themes/minimal.toml
    exec strace -ff -qq -e trace=process -o $scratch/direct.trace $bundle/bin/zsh -d
  fi
  export ZDOTDIR=$user_zdotdir
  export WSH_STATE_ROOT=$state_root
  unset WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  exec strace -ff -qq -e trace=process -o $scratch/managed.trace $manager run --state-root $state_root
}

pty_read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

local variant
for variant in direct managed; do
  current_variant=$variant
  current_pty=wsh_config_process_${variant}_${$}
  pty_output=
  zpty -b $current_pty trace_child
  local -F deadline=$(( EPOCHREALTIME + 8 ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    [[ $pty_output == *git:main* ]] && break
    zselect -t 1 2>/dev/null || true
  done
  [[ $pty_output == *git:main* ]] || {
    print -u2 -r -- "timeout waiting for $variant startup: ${(qqq)pty_output}"
    exit 1
  }
  zpty -w $current_pty exit
  zselect -t 20 2>/dev/null || true
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
done

print -r -- $'variant\tcount\texecutable' > $stage
for variant in direct managed; do
  local record count executable
  while IFS= read -r record; do
    count=${record%% *}
    executable=${record#* }
    executable=${executable:t}
    printf '%s\t%d\t%s\n' $variant $count $executable >> $stage
  done < <(sed -n 's/.*execve("\([^"]*\)".* = 0$/\1/p' $scratch/${variant}.trace.* | sort | uniq -c | sed 's/^[[:space:]]*//')
done

mv -- $stage $output
trap - EXIT INT TERM
command rm -rf -- $scratch
print -r -- $output
