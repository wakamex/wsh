#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 4 )) || {
  print -u2 -- 'usage: benchmark-edge-zsh-defaults-startup.zsh OUTPUT MANAGER STABLE_BUNDLE EDGE_BUNDLE'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly stable_bundle=${3:A}
readonly edge_bundle=${4:A}
readonly repetitions=20
readonly warmups=5
readonly cpu=${WSH_DEFAULTS_STARTUP_CPU:-0}
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

readonly scratch=$(mktemp -d /var/tmp/wsh-edge-defaults-startup.XXXXXX)
readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
readonly fixture=$scratch/fixture
typeset -g current_pty= pty_output= current_home= current_state_root=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $scratch $stage
}
trap cleanup EXIT INT TERM

command git init -q -b main $fixture
command git -C $fixture config user.name 'wsh edge defaults benchmark'
command git -C $fixture config user.email edge-defaults@wsh.invalid
print -r -- tracked > $fixture/tracked
command git -C $fixture add tracked
command git -C $fixture commit -qm initial
$manager bundle activate $stable_bundle --state-root $scratch/state-stable >/dev/null
$manager bundle activate $edge_bundle --state-root $scratch/state-edge >/dev/null

local build variant home
for build in stable edge; do
  for variant in disabled history autosuggestions syntax all; do
    home=$scratch/home-$build-$variant
    command mkdir -p -- $home
    case $variant in
      disabled)
        print -r -- 'typeset -g WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1 WSH_DISABLE_AUTOSUGGESTIONS=1 WSH_DISABLE_SYNTAX_HIGHLIGHTING=1' > $home/.zshrc
        ;;
      history)
        print -r -- 'typeset -g WSH_DISABLE_AUTOSUGGESTIONS=1 WSH_DISABLE_SYNTAX_HIGHLIGHTING=1' > $home/.zshrc
        ;;
      autosuggestions)
        print -r -- 'typeset -g WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1 WSH_DISABLE_SYNTAX_HIGHLIGHTING=1' > $home/.zshrc
        ;;
      syntax)
        print -r -- 'typeset -g WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1 WSH_DISABLE_AUTOSUGGESTIONS=1' > $home/.zshrc
        ;;
      all)
        : > $home/.zshrc
        ;;
    esac
  done
done

pty_read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

startup_child() {
  builtin cd -q -- $fixture
  export HOME=$current_home
  export ZDOTDIR=$current_home
  export WSH_STATE_ROOT=$current_state_root
  export TERM=xterm-256color
  command stty -echo
  exec taskset -c $cpu $manager run --state-root $current_state_root
}

measure_startup() {
  local build=$1 variant=$2 block=$3 position=$4 repetition=$5 record=$6
  current_home=$scratch/home-$build-$variant
  current_state_root=$scratch/state-$build
  current_pty=wsh_edge_defaults_${$}_${block}_${position}_${repetition}
  pty_output=
  local -F started=$EPOCHREALTIME deadline elapsed_ms
  zpty -b $current_pty startup_child
  local pty_fd=$REPLY
  deadline=$(( started + 5 ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    if [[ $pty_output == *'% '* ]]; then
      elapsed_ms=$(( (EPOCHREALTIME - started) * 1000 ))
      (( record )) && printf '%s\t%s\t%s\t%d\t%s\t%d\t%.6f\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $build $block $position $variant $repetition $elapsed_ms >> $stage
      zpty -w $current_pty "zmodload zsh/zleparameter; print -r -- WSH_DEFAULT_STATE:\${WSH_HISTORY_SUBSTRING_SEARCH_OWNER-unset}:\${WSH_AUTOSUGGESTIONS_OWNER-unset}:\${WSH_SYNTAX_HIGHLIGHTING_OWNER-unset}:\$(( \$+widgets[history-substring-search-up] )):\$(( \$+widgets[autosuggest-fetch] )):\$(( \$+functions[_zsh_highlight] ))"
      local expected
      case $variant in
        disabled) expected='WSH_DEFAULT_STATE:disabled:disabled:disabled:0:0:0' ;;
        history) expected='WSH_DEFAULT_STATE:wsh:disabled:disabled:1:0:1' ;;
        autosuggestions) expected='WSH_DEFAULT_STATE:disabled:wsh:disabled:0:1:0' ;;
        syntax) expected='WSH_DEFAULT_STATE:disabled:disabled:wsh:0:0:1' ;;
        all) expected='WSH_DEFAULT_STATE:wsh:wsh:wsh:1:1:1' ;;
      esac
      local -F state_deadline=$(( EPOCHREALTIME + 3 ))
      while (( EPOCHREALTIME < state_deadline )); do
        pty_read_available
        [[ $pty_output == *$expected* ]] && break
        zselect -r $pty_fd -t 1 2>/dev/null || true
      done
      [[ $pty_output == *$expected* ]] || {
        print -u2 -r -- "unexpected $build $variant state: ${(qqq)pty_output}"
        return 1
      }
      zpty -w $current_pty exit
      zselect -r $pty_fd -t 100 2>/dev/null || true
      zpty -d $current_pty 2>/dev/null || true
      current_pty=
      return 0
    fi
    zselect -r $pty_fd -t 1 2>/dev/null || true
  done
  print -u2 -r -- "timeout waiting for $build $variant: ${(qqq)pty_output}"
  return 1
}

print -r -- $'measured_at_utc\tbuild\tblock\tposition\tvariant\trepetition\tfirst_editable_ms' > $stage
local specification repetition block position
local -a variants=(disabled history autosuggestions syntax all)
local -a order
for build in stable edge; do
  for variant in $variants; do
    for repetition in {1..$warmups}; do
      measure_startup $build $variant warmup 0 $repetition 0
    done
  done
done
for block in forward reverse; do
  if [[ $block == forward ]]; then
    order=(stable-disabled edge-disabled stable-history edge-history stable-autosuggestions edge-autosuggestions stable-syntax edge-syntax stable-all edge-all)
  else
    order=(edge-all stable-all edge-syntax stable-syntax edge-autosuggestions stable-autosuggestions edge-history stable-history edge-disabled stable-disabled)
  fi
  position=0
  for specification in $order; do
    build=${specification%%-*}
    variant=${specification#*-}
    (( ++position ))
    for repetition in {1..$repetitions}; do
      measure_startup $build $variant $block $position $repetition 1
    done
  done
done

mv -- $stage $output
trap - EXIT INT TERM
command rm -rf -- $scratch
print -r -- $output
