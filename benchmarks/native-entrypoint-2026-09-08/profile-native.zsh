#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect
export WSH_THEME=minimal

readonly manager=${1:A}
readonly bundle=${2:A}
readonly scratch=$(mktemp -d /tmp/wsh-profile-test.XXXXXX)
readonly state_root=${scratch}/state
readonly home=${scratch}/home
readonly fixture=${scratch}/fixture
readonly pty_name=wsh_profile_${RANDOM}_${$}
typeset -g pty_output=

cleanup() {
  zpty -d $pty_name 2>/dev/null || true
  command rm -rf -- $scratch
}
trap cleanup EXIT INT TERM

command mkdir -p -- $home $fixture
command git -C $fixture init -q -b main
command git -C $fixture config user.name 'wsh profile test'
command git -C $fixture config user.email profile-test@wsh.invalid
print -r -- seed > $fixture/tracked
command git -C $fixture add tracked
command git -C $fixture commit -qm initial
print -r -- 'typeset -g WSH_PROFILE_SECRET_ZSHENV=profile-secret-zshenv' > $home/.zshenv
print -r -- 'typeset -g WSH_PROFILE_SECRET_ZSHRC=profile-secret-zshrc' > $home/.zshrc
$manager bundle activate $bundle --state-root $state_root >/dev/null

# A build host can hide broken relocation through Zsh's compiled module path.
# Exercise the real adapter with that fallback unavailable before any modules load.
HOME=$home ZDOTDIR=$home $bundle/bin/zsh -dfc '
  unset WSH_USER_ZDOTDIR WSH_RUN_FOREGROUND
  module_path=()
  WSH_BUNDLE_ROOT=$1
  WSH_PROFILE_FILE=$2/relocation.jsonl
  WSH_PROFILE_ZPROF_FILE=$2/relocation-zprof.txt
  WSH_PROFILE_STARTED_AT=0
  WSH_PROFILE_FUNCTIONS=1
  : > $WSH_PROFILE_FILE
  source $WSH_BUNDLE_ROOT/share/wsh/native-before.zsh
  for module in datetime system stat zprof; do
    zmodload -e zsh/$module || exit 1
  done
  (( $+functions[_wsh_profile_event] )) || exit 1
  _wsh_profile_event editor-ready
  _wsh_profile_flush
  [[ $(< $WSH_PROFILE_FILE) == *editor-ready* ]] || exit 1
' wsh-profile-relocation $bundle $scratch || {
  print -u2 -- 'error: profiling requires the unavailable compiled module path'
  return 1
}

profile_child() {
  builtin cd -q -- $fixture
  export HOME=$home ZDOTDIR=$home TERM=xterm-256color WSH_STATE_ROOT=$state_root
  command stty -echo
  exec $manager profile --functions --state-root $state_root
}

read_available() {
  local chunk
  while zpty -r -t $pty_name chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

wait_for() {
  local expected=$1
  local -F deadline=$(( EPOCHREALTIME + ${2:-5} ))
  while (( EPOCHREALTIME < deadline )); do
    read_available
    [[ $pty_output == *$expected* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  read_available
  print -u2 -r -- "timeout waiting for ${(qqq)expected}: ${(qqq)pty_output}"
  return 1
}

zpty -b $pty_name profile_child
wait_for 'Profiling this shell.'
wait_for 'git:main'
local -a profile_directories
profile_directories=($state_root/profiles/*(/N))
(( ${#profile_directories} == 1 )) || {
  print -u2 -- "expected one live profile directory, found ${#profile_directories}"
  return 1
}
readonly profile_directory=$profile_directories[1]
local live_report=
local -F report_deadline=$(( EPOCHREALTIME + 2 ))
while (( EPOCHREALTIME < report_deadline )); do
  live_report=$($manager profile report $profile_directory) || true
  [[ $live_report == *'Wsh ZLE initialization hook:'* && $live_report == *'Snapshot published:'* ]] && break
  zselect -t 1 2>/dev/null || true
done
[[ $live_report == *'Wsh ZLE initialization hook:'* && $live_report == *'Snapshot published:'* ]] || {
  print -u2 -r -- "live profile could not be recovered before shell exit: ${(qqq)live_report}"
  return 1
}
pty_output=
zpty -w $pty_name ':'
wait_for 'git:main'
zpty -w $pty_name exit
wait_for 'Wsh profile'
wait_for 'Slowest Zsh functions by self time'
wait_for 'Trace:'
zpty -d $pty_name

(( ${#profile_directories} == 1 )) || {
  print -u2 -- "expected one profile directory, found ${#profile_directories}"
  return 1
}
readonly trace=$profile_directory/trace.jsonl
readonly zprof=$profile_directory/zprof.txt

[[ $(stat -c %a $state_root/profiles) == 700 && $(stat -c %a $profile_directory) == 700 ]]
[[ $(stat -c %a $trace) == 600 && $(stat -c %a $zprof) == 600 ]]
[[ $(stat -c %s $trace) -le $(( 8 * 1024 * 1024 )) && $(stat -c %s $zprof) -le $(( 1024 * 1024 )) ]]
[[ -s $trace && -s $zprof ]]

local report
report=$($manager profile report $profile_directory)
for expected in \
  'Wsh ZLE initialization hook:' \
  'Launcher to Zsh startup:' \
  'User .zshenv:' \
  'User .zshrc:' \
  'History substring search:' \
  'Autosuggestions:' \
  'Syntax highlighting:' \
  'Wsh integration:' \
  'Wsh first precmd hook:' \
  'Runtime ready:' \
  'Repository discovery:' \
  'Git process:' \
  'Git output parsing:' \
  'Provider total:' \
  'Child processes: 1' \
  'Prompt rendering:' \
  'Response write:' \
  'Snapshot published:' \
  'Snapshot applied and repainted:' \
  'History substring search: wsh' \
  'Autosuggestions: wsh' \
  'Syntax highlighting: wsh' \
  'Theme: minimal'; do
  [[ $report == *$expected* ]] || {
    print -u2 -r -- "profile report is missing ${(qqq)expected}: ${(qqq)report}"
    return 1
  }
done

[[ $(< $trace) != *profile-secret-zshenv* && $(< $trace) != *profile-secret-zshrc* && $(< $trace) != *$fixture* ]]
[[ $(< $trace) != *'"command"'* && $(< $trace) != *'"prompt"'* && $(< $trace) != *'"cwd"'* ]]

local profile_count_before=${#profile_directories}
HOME=$home ZDOTDIR=$home TERM=xterm-256color WSH_STATE_ROOT=$state_root \
  $manager run --state-root $state_root -- -ic exit >/dev/null 2>&1
profile_directories=($state_root/profiles/*(/N))
(( ${#profile_directories} == profile_count_before )) || {
  print -u2 -- 'ordinary wsh startup created profile storage'
  return 1
}

cp $trace $scratch/malformed.jsonl
print -rn -- '{' >> $scratch/malformed.jsonl
command mv $scratch/malformed.jsonl $profile_directory/trace.jsonl
if $manager profile report $profile_directory >/dev/null 2>&1; then
  print -u2 -- 'profile report accepted an incomplete trace event'
  return 1
fi

print -r -- 'PASS: private end-to-end profile attributes startup, Zsh functions, provider work, rendering, IPC, and first editor readiness without command or path capture'
