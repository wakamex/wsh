#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 6 )) || {
  print -u2 -- 'usage: benchmark-syntax-highlighting-edit.zsh OUTPUT MANAGER BUNDLE SYNTAX-REPOSITORY baseline|candidate CPU'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly bundle=${3:A}
readonly plugin_repository=${4:A}
readonly expectation=$5
readonly cpu=$6
readonly plugin_revision=2fc57d63067c18b1100ecdbf684fa5baf49459d1
readonly repetitions=50
readonly warmups=10

[[ ! -e $output && ! -L $output && -x $manager && -x $bundle/bin/zsh && ( $expectation == baseline || $expectation == candidate ) ]] || {
  print -u2 -- 'error: output must be new and manager, bundle, or expectation is invalid'
  exit 2
}
git -C $plugin_repository cat-file -e ${plugin_revision}^{commit} 2>/dev/null || {
  print -u2 -- "error: plugin revision is unavailable: $plugin_revision"
  exit 2
}

readonly benchmark_root=$(mktemp -d /var/tmp/wsh-syntax-edit.XXXXXX)
readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
readonly plugin=$benchmark_root/plugin
readonly state_root=$benchmark_root/state
readonly fixture=$benchmark_root/fixture
typeset -g current_pty= pty_output= current_home= current_log=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $benchmark_root $stage
}
trap cleanup EXIT INT TERM

command mkdir -p -- $plugin $state_root $fixture
git -C $plugin_repository archive $plugin_revision | tar -xf - -C $plugin
$manager bundle activate $bundle --state-root $state_root >/dev/null
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh syntax highlighting edit benchmark'
git -C $fixture config user.email syntax-edit@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial

local variant home
for variant in external-ready clean external; do
  home=$benchmark_root/home-$variant
  command mkdir -p -- $home
  print -r -- 'typeset -g WSH_DISABLE_AUTOSUGGESTIONS=1
typeset -gA ZSH_HIGHLIGHT_STYLES
ZSH_HIGHLIGHT_STYLES[arg0]=fg=blue
ZSH_HIGHLIGHT_STYLES[single-quoted-argument]=fg=yellow
ZSH_HIGHLIGHT_STYLES[double-quoted-argument]=fg=yellow' >| $home/.zshrc
  if [[ $variant == external-ready ]]; then
    print -r -- "zmodload zsh/zle
source ${(q)plugin}/zsh-syntax-highlighting.zsh" >> $home/.zshrc
  elif [[ $variant == external ]]; then
    print -r -- "source ${(q)plugin}/zsh-syntax-highlighting.zsh" >> $home/.zshrc
  fi
  print -r -- '_wsh_syntax_benchmark_report() {
  BUFFER=""
  region_highlight=()
  zle .accept-line
}
_wsh_syntax_benchmark_set_short() {
  BUFFER="print \"WSH_HIGHLIGHT_END\""
  CURSOR=$#BUFFER
}
_wsh_syntax_benchmark_set_long() {
  BUFFER="print \"${(l:975::x:)}WSH_HIGHLIGHT_END\""
  CURSOR=$#BUFFER
}
_wsh_syntax_benchmark_after_highlight() {
  if [[ $BUFFER == *WSH_HIGHLIGHT_END\" ]]; then
    print -r -- "${(j:,:)region_highlight}" >> $WSH_SYNTAX_BENCHMARK_LOG
  fi
}
_wsh_syntax_benchmark_install_hook() {
  local -a redraw_hooks=()
  zstyle -a zle-line-pre-redraw widgets redraw_hooks
  if (( ${#${(M)redraw_hooks:#*:_zsh_highlight__zle-line-pre-redraw}} )); then
    autoload -Uz add-zle-hook-widget add-zsh-hook
    add-zle-hook-widget zle-line-pre-redraw _wsh_syntax_benchmark_after_highlight
    add-zsh-hook -d precmd _wsh_syntax_benchmark_install_hook
  fi
}
zle -N _wsh_syntax_benchmark_report
zle -N _wsh_syntax_benchmark_set_short
zle -N _wsh_syntax_benchmark_set_long
bindkey -M emacs "^G" _wsh_syntax_benchmark_report
bindkey -M emacs "^Xs" _wsh_syntax_benchmark_set_short
bindkey -M emacs "^Xl" _wsh_syntax_benchmark_set_long' >> $home/.zshrc
  print -r -- 'autoload -Uz add-zsh-hook
add-zsh-hook precmd _wsh_syntax_benchmark_install_hook' >> $home/.zshrc
done

pty_read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

pty_wait_for() {
  local expected=$1 label=$2
  local -F deadline=$(( EPOCHREALTIME + 8 ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    [[ $pty_output == *$expected* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -r -- "timeout waiting for ${label}: output-bytes=${#pty_output}"
  return 1
}

wait_for_lines() {
  local expected=$1
  local -F deadline=$(( EPOCHREALTIME + 3 ))
  while (( EPOCHREALTIME < deadline )); do
    [[ $(wc -l < $current_log) -ge $expected ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -- "timeout waiting for ${expected} highlight reports"
  return 1
}

edit_child() {
  builtin cd -q -- $fixture
  export HOME=$current_home
  export ZDOTDIR=$current_home
  export WSH_STATE_ROOT=$state_root
  export WSH_SYNTAX_BENCHMARK_LOG=$current_log
  export TERM=xterm-256color
  unset EDITOR VISUAL WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  exec taskset -c $cpu $manager run --state-root $state_root
}

run_variant() {
  local variant=$1 block=$2 position=$3
  current_home=$benchmark_root/home-$variant
  current_log=$benchmark_root/$variant-$block.log
  : >| $current_log
  current_pty=wsh_syntax_edit_${$}_${block}_${position}
  pty_output=
  zpty -b $current_pty edit_child
  pty_wait_for git:main prompt
  pty_output=
  zpty -w $current_pty :
  pty_wait_for git:main hook-installation-prompt

  local workload keys record repetition expected_lines=0
  local -F started elapsed_ms
  for workload keys in short $'\x18s' long $'\x18l'; do
    for record in 0 1; do
      local limit=$warmups
      (( record )) && limit=$repetitions
      for repetition in {1..$limit}; do
        pty_output=
        started=$EPOCHREALTIME
        zpty -w -n $current_pty $keys
        (( ++expected_lines ))
        wait_for_lines $expected_lines
        elapsed_ms=$(( (EPOCHREALTIME - started) * 1000 ))
        local highlights=$(sed -n "${expected_lines}p" $current_log)
        [[ $highlights == *fg=blue* && $highlights == *fg=yellow* ]] || {
          print -u2 -r -- "missing configured highlight for ${variant} ${workload}: ${(qqq)highlights}"
          return 1
        }
        zpty -w -n $current_pty $'\x07'
        pty_output=
        pty_wait_for git:main prompt
        if (( record )); then
          printf '%s\t%s\t%s\t%d\t%s\t%s\t%d\t%.6f\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $expectation $block $position $variant $workload $repetition $elapsed_ms >> $stage
        fi
      done
    done
  done

  zpty -w $current_pty exit
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
}

print -r -- $'measured_at_utc\tbuild\tblock\tposition\tvariant\tworkload\trepetition\tredraw_ms' > $stage
local -a variants
if [[ $expectation == baseline ]]; then
  variants=(external-ready)
else
  variants=(clean external)
fi
local -a order
local block position
for block in forward reverse; do
  if [[ $block == forward ]]; then
    order=($variants)
  else
    order=(${(Oa)variants})
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
