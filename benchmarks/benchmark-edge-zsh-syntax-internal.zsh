#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 4 )) || {
  print -u2 -- 'usage: benchmark-edge-zsh-syntax-internal.zsh OUTPUT MANAGER STABLE_BUNDLE EDGE_BUNDLE'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly stable_bundle=${3:A}
readonly edge_bundle=${4:A}
readonly repetitions=50
readonly warmups=10
readonly cpu=${WSH_SYNTAX_INTERNAL_CPU:-0}
[[ ! -e $output && ! -L $output && -x $manager ]] || {
  print -u2 -- 'error: output must be new and manager must be executable'
  exit 2
}
for bundle in $stable_bundle $edge_bundle; do
  [[ -x $bundle/bin/zsh && -x $bundle/bin/wsh-runtime ]] || {
    print -u2 -- "error: incomplete bundle: $bundle"
    exit 2
  }
done

readonly scratch=$(mktemp -d /var/tmp/wsh-edge-syntax-internal.XXXXXX)
readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
readonly fixture=$scratch/fixture
typeset -g current_pty= pty_output= current_home= current_state_root= current_log=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $scratch $stage
}
trap cleanup EXIT INT TERM

command git init -q -b main $fixture
command git -C $fixture config user.name 'wsh edge syntax benchmark'
command git -C $fixture config user.email edge-syntax@wsh.invalid
print -r -- tracked > $fixture/tracked
command git -C $fixture add tracked
command git -C $fixture commit -qm initial
$manager bundle activate $stable_bundle --state-root $scratch/state-stable >/dev/null
$manager bundle activate $edge_bundle --state-root $scratch/state-edge >/dev/null

local build home
for build in stable edge; do
  home=$scratch/home-$build
  command mkdir -p -- $home
  print -r -- 'typeset -g WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1 WSH_DISABLE_AUTOSUGGESTIONS=1
typeset -gA ZSH_HIGHLIGHT_STYLES
ZSH_HIGHLIGHT_STYLES[arg0]=fg=blue
ZSH_HIGHLIGHT_STYLES[single-quoted-argument]=fg=yellow
ZSH_HIGHLIGHT_STYLES[double-quoted-argument]=fg=yellow
typeset -gF WSH_EDGE_SYNTAX_STARTED_AT=0
_wsh_edge_syntax_set_short() {
  WSH_EDGE_SYNTAX_STARTED_AT=$EPOCHREALTIME
  BUFFER="print \"WSH_HIGHLIGHT_END\""
  CURSOR=$#BUFFER
}
_wsh_edge_syntax_set_long() {
  WSH_EDGE_SYNTAX_STARTED_AT=$EPOCHREALTIME
  BUFFER="print \"${(l:975::x:)}WSH_HIGHLIGHT_END\""
  CURSOR=$#BUFFER
}
_wsh_edge_syntax_after() {
  if (( WSH_EDGE_SYNTAX_STARTED_AT > 0 )) && [[ $BUFFER == *WSH_HIGHLIGHT_END\" ]]; then
    printf "%.9f\t%s\n" $(( (EPOCHREALTIME - WSH_EDGE_SYNTAX_STARTED_AT) * 1000 )) "${(j:,:)region_highlight}" >> $WSH_EDGE_SYNTAX_LOG
    WSH_EDGE_SYNTAX_STARTED_AT=0
  fi
}
_wsh_edge_syntax_reset() {
  BUFFER=""
  region_highlight=()
  zle .accept-line
}
_wsh_edge_syntax_install_observer() {
  local -a redraw_hooks=()
  zstyle -a zle-line-pre-redraw widgets redraw_hooks
  if (( ${#${(M)redraw_hooks:#*:_zsh_highlight__zle-line-pre-redraw}} )); then
    autoload -Uz add-zle-hook-widget add-zsh-hook
    add-zle-hook-widget zle-line-pre-redraw _wsh_edge_syntax_after
    add-zsh-hook -d precmd _wsh_edge_syntax_install_observer
  fi
}
zle -N _wsh_edge_syntax_set_short
zle -N _wsh_edge_syntax_set_long
zle -N _wsh_edge_syntax_reset
bindkey -M emacs "^Xs" _wsh_edge_syntax_set_short
bindkey -M emacs "^Xl" _wsh_edge_syntax_set_long
bindkey -M emacs "^G" _wsh_edge_syntax_reset
autoload -Uz add-zsh-hook
add-zsh-hook precmd _wsh_edge_syntax_install_observer' > $home/.zshrc
done

pty_read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

pty_wait_for() {
  local expected=$1
  local -F deadline=$(( EPOCHREALTIME + 5 ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    [[ $pty_output == *$expected* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -r -- "timeout waiting for ${(qqq)expected}: output-bytes=${#pty_output}"
  return 1
}

wait_for_lines() {
  local expected=$1
  local -F deadline=$(( EPOCHREALTIME + 3 ))
  while (( EPOCHREALTIME < deadline )); do
    [[ $(wc -l < $current_log) -ge $expected ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -- "timeout waiting for $expected internal timing records"
  return 1
}

syntax_child() {
  builtin cd -q -- $fixture
  export HOME=$current_home
  export ZDOTDIR=$current_home
  export WSH_STATE_ROOT=$current_state_root
  export WSH_EDGE_SYNTAX_LOG=$current_log
  export TERM=xterm-256color
  command stty -echo
  exec taskset -c $cpu $manager run --state-root $current_state_root
}

run_session() {
  local build=$1 block=$2 position=$3
  current_home=$scratch/home-$build
  current_state_root=$scratch/state-$build
  current_log=$scratch/$build-$block.log
  : > $current_log
  current_pty=wsh_edge_syntax_${$}_${block}_${position}
  pty_output=
  zpty -b $current_pty syntax_child
  pty_wait_for git:main
  pty_output=
  zpty -w $current_pty :
  pty_wait_for git:main

  local workload keys record repetition expected_lines=0 result elapsed regions
  local -a workloads
  [[ $block == forward ]] && workloads=(short long) || workloads=(long short)
  for workload in $workloads; do
    [[ $workload == short ]] && keys=$'\x18s' || keys=$'\x18l'
    for record in 0 1; do
      local limit=$warmups
      (( record )) && limit=$repetitions
      for repetition in {1..$limit}; do
        zpty -w -n $current_pty $keys
        (( ++expected_lines ))
        wait_for_lines $expected_lines
        result=$(sed -n "${expected_lines}p" $current_log)
        elapsed=${result%%$'\t'*}
        regions=${result#*$'\t'}
        [[ $elapsed == <->.<-> && $regions == *fg=blue* && $regions == *fg=yellow* ]] || {
          print -u2 -r -- "invalid $build $workload record: ${(qqq)result}"
          return 1
        }
        zpty -w -n $current_pty $'\x07'
        pty_output=
        pty_wait_for git:main
        (( record )) && printf '%s\t%s\t%s\t%d\t%s\t%d\t%s\n' \
          "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $build $block $position $workload $repetition $elapsed >> $stage
      done
    done
  done
  zpty -w $current_pty exit
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
}

print -r -- $'measured_at_utc\tbuild\tblock\tposition\tworkload\trepetition\tinternal_redraw_ms' > $stage
local block position
local -a order
for block in forward reverse; do
  [[ $block == forward ]] && order=(stable edge) || order=(edge stable)
  position=0
  for build in $order; do
    (( ++position ))
    run_session $build $block $position
  done
done

mv -- $stage $output
trap - EXIT INT TERM
command rm -rf -- $scratch
print -r -- $output
