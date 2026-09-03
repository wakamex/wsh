#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 6 )) || {
  print -u2 -- 'usage: benchmark-autosuggestions-prompt.zsh OUTPUT MANAGER BUNDLE AUTOSUGGESTIONS-REPOSITORY baseline|candidate CPU'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly bundle=${3:A}
readonly plugin_repository=${4:A}
readonly expectation=$5
readonly cpu=$6
readonly plugin_revision=85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5
readonly repetitions=100
readonly warmups=10

[[ ! -e $output && ! -L $output && -x $manager && -x $bundle/bin/zsh && ( $expectation == baseline || $expectation == candidate ) ]] || {
  print -u2 -- 'error: output must be new and manager, bundle, or expectation is invalid'
  exit 2
}
git -C $plugin_repository cat-file -e ${plugin_revision}^{commit} 2>/dev/null || {
  print -u2 -- "error: plugin revision is unavailable: $plugin_revision"
  exit 2
}

readonly benchmark_root=$(mktemp -d /var/tmp/wsh-autosuggestions-prompt.XXXXXX)
readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
readonly plugin=$benchmark_root/plugin
readonly state_root=$benchmark_root/state
readonly fixture=$benchmark_root/fixture
typeset -g current_pty= pty_output= current_home=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $benchmark_root $stage
}
trap cleanup EXIT INT TERM

command mkdir -p -- $plugin $state_root $fixture
git -C $plugin_repository archive $plugin_revision | tar -xf - -C $plugin
$manager bundle activate $bundle --state-root $state_root >/dev/null
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh autosuggestions prompt benchmark'
git -C $fixture config user.email autosuggestions-prompt@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial

local variant home
for variant in disabled clean external external-manual; do
  home=$benchmark_root/home-$variant
  command mkdir -p -- $home
  case $variant in
    disabled) print -r -- 'typeset -g WSH_DISABLE_AUTOSUGGESTIONS=1' >| $home/.zshrc ;;
    clean) : >| $home/.zshrc ;;
    external) print -r -- "source ${(q)plugin}/zsh-autosuggestions.zsh" >| $home/.zshrc ;;
    external-manual) print -r -- "typeset -g ZSH_AUTOSUGGEST_MANUAL_REBIND=1
source ${(q)plugin}/zsh-autosuggestions.zsh" >| $home/.zshrc ;;
  esac
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
    [[ $pty_output == *git:main* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -r -- "timeout waiting for prompt: ${(qqq)pty_output}"
  return 1
}

prompt_child() {
  builtin cd -q -- $fixture
  export HOME=$current_home
  export ZDOTDIR=$current_home
  export WSH_STATE_ROOT=$state_root
  export TERM=xterm-256color
  unset EDITOR VISUAL WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  exec taskset -c $cpu $manager run --state-root $state_root
}

run_variant() {
  local variant=$1 block=$2 position=$3
  current_home=$benchmark_root/home-$variant
  current_pty=wsh_autosuggestions_prompt_${$}_${block}_${position}
  pty_output=
  zpty -b $current_pty prompt_child
  local pty_fd=$REPLY
  pty_wait_for_prompt

  local repetition record
  for record in 0 1; do
    local limit=$warmups
    (( record )) && limit=$repetitions
    for repetition in {1..$limit}; do
      pty_output=
      local -F started=$EPOCHREALTIME elapsed_ms
      zpty -w $current_pty :
      pty_wait_for_prompt
      elapsed_ms=$(( (EPOCHREALTIME - started) * 1000 ))
      if (( record )); then
        printf '%s\t%s\t%s\t%d\t%s\t%d\t%.6f\n' \
          "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $expectation $block $position $variant $repetition $elapsed_ms >> $stage
      fi
      zselect -r $pty_fd -t 1 2>/dev/null || true
      pty_read_available
    done
  done

  zpty -w $current_pty exit
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
}

print -r -- $'measured_at_utc\tbuild\tblock\tposition\tvariant\trepetition\tprompt_ms' > $stage
local -a variants
if [[ $expectation == baseline ]]; then
  variants=(clean external external-manual)
else
  variants=(disabled clean external)
fi
local -a order
local block position
for block in forward reverse; do
  if [[ $block == forward ]]; then
    order=($variants)
  elif [[ $expectation == baseline ]]; then
    order=(external-manual external clean)
  else
    order=(external clean disabled)
  fi
  position=0
  for variant in $order; do
    (( ++position ))
    run_variant $variant $block $position
  done
done

mv -- $stage $output
trap - EXIT INT TERM
command rm -rf -- $benchmark_root
print -r -- $output
