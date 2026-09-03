#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail -o typeset_silent
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 6 )) || {
  print -u2 -- 'usage: benchmark-syntax-highlighting-startup.zsh OUTPUT MANAGER BASELINE-BUNDLE CANDIDATE-BUNDLE SYNTAX-REPOSITORY CPU'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly baseline_bundle=${3:A}
readonly candidate_bundle=${4:A}
readonly plugin_repository=${5:A}
readonly cpu=$6
readonly plugin_revision=2fc57d63067c18b1100ecdbf684fa5baf49459d1
readonly repetitions=20
readonly warmups=5

[[ ! -e $output && ! -L $output && -x $manager && -x $baseline_bundle/bin/zsh && -x $candidate_bundle/bin/zsh ]] || {
  print -u2 -- 'error: output must be new and manager or bundles are invalid'
  exit 2
}
git -C $plugin_repository cat-file -e ${plugin_revision}^{commit} 2>/dev/null || {
  print -u2 -- "error: plugin revision is unavailable: $plugin_revision"
  exit 2
}

readonly benchmark_root=$(mktemp -d /var/tmp/wsh-syntax-startup.XXXXXX)
readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
readonly plugin=$benchmark_root/plugin
readonly baseline_state_root=$benchmark_root/baseline-state
readonly candidate_state_root=$benchmark_root/candidate-state
readonly fixture=$benchmark_root/fixture
typeset -g current_pty= pty_output= current_home= current_state_root= current_bundle=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $benchmark_root $stage
}
trap cleanup EXIT INT TERM

command mkdir -p -- $plugin $baseline_state_root $candidate_state_root $fixture
git -C $plugin_repository archive $plugin_revision | tar -xf - -C $plugin
$manager bundle activate $baseline_bundle --state-root $baseline_state_root >/dev/null
$manager bundle activate $candidate_bundle --state-root $candidate_state_root >/dev/null
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh syntax highlighting startup benchmark'
git -C $fixture config user.email syntax-startup@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial

local variant home configuration
for variant in baseline-clean baseline-external baseline-external-ready candidate-disabled candidate-clean candidate-external candidate-external-ready; do
  home=$benchmark_root/home-$variant
  command mkdir -p -- $home
  configuration=${variant#*-}
  case $configuration in
    disabled) print -r -- 'typeset -g WSH_DISABLE_SYNTAX_HIGHLIGHTING=1' >| $home/.zshrc ;;
    clean) : >| $home/.zshrc ;;
    external) print -r -- "source ${(q)plugin}/zsh-syntax-highlighting.zsh" >| $home/.zshrc ;;
    external-ready) print -r -- "zmodload zsh/zle
source ${(q)plugin}/zsh-syntax-highlighting.zsh" >| $home/.zshrc ;;
  esac
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
  unset EDITOR VISUAL WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  exec taskset -c $cpu $manager run --state-root $current_state_root
}

measure_startup() {
  local variant=$1 block=$2 position=$3 repetition=$4 record=$5
  current_home=$benchmark_root/home-$variant
  local build=${variant%%-*}
  local configuration=${variant#*-}
  if [[ $build == baseline ]]; then
    current_bundle=$baseline_bundle
    current_state_root=$baseline_state_root
  else
    current_bundle=$candidate_bundle
    current_state_root=$candidate_state_root
  fi
  current_pty=wsh_syntax_startup_${$}_${block}_${position}_${repetition}
  pty_output=
  local -F started=$EPOCHREALTIME deadline elapsed_ms
  zpty -b $current_pty startup_child
  local pty_fd=$REPLY
  deadline=$(( started + 8 ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    if [[ $pty_output == *git:main* ]]; then
      elapsed_ms=$(( (EPOCHREALTIME - started) * 1000 ))
      if (( record )); then
        printf '%s\t%s\t%s\t%d\t%s\t%d\t%.6f\n' \
          "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $build $block $position $configuration $repetition $elapsed_ms >> $stage
      fi
      zpty -w $current_pty "zmodload zsh/parameter; typeset -a redraw_hooks=(); zstyle -a zle-line-pre-redraw widgets redraw_hooks; typeset highlight_source=none; (( \${+ZSH_HIGHLIGHT_VERSION} )) && highlight_source=\$functions_source[_zsh_highlight]; print -r -- \$'WSH_\\x53YNTAX_STATE:'\${ZSH_HIGHLIGHT_VERSION-unset}:\${#\${(M)redraw_hooks:#*:_zsh_highlight__zle-line-pre-redraw}}:\${WSH_SYNTAX_HIGHLIGHTING_OWNER-unset}:\$highlight_source"
      local expected_state
      if [[ $build == baseline ]]; then
        expected_state=WSH_SYNTAX_STATE:unset:0:unset:none
        [[ $configuration == external ]] && expected_state=WSH_SYNTAX_STATE:0.8.1-dev:0:unset:${plugin}/zsh-syntax-highlighting.zsh
        [[ $configuration == external-ready ]] && expected_state=WSH_SYNTAX_STATE:0.8.1-dev:1:unset:${plugin}/zsh-syntax-highlighting.zsh
      else
        case $configuration in
          disabled) expected_state=WSH_SYNTAX_STATE:unset:0:disabled:none ;;
          clean) expected_state=WSH_SYNTAX_STATE:0.8.1-dev:1:wsh:${candidate_bundle}/share/wsh/defaults/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ;;
          external|external-ready) expected_state=WSH_SYNTAX_STATE:0.8.1-dev:1:external-exact:${plugin}/zsh-syntax-highlighting.zsh ;;
        esac
      fi
      local -F state_deadline=$(( EPOCHREALTIME + 3 ))
      while (( EPOCHREALTIME < state_deadline )); do
        pty_read_available
        [[ $pty_output == *$expected_state* ]] && break
        zselect -r $pty_fd -t 1 2>/dev/null || true
      done
      [[ $pty_output == *$expected_state* ]] || {
        print -u2 -r -- "unexpected $variant state: ${(qqq)pty_output}"
        return 1
      }
      [[ $pty_output != *'no such file or directory'* ]] || {
        print -u2 -r -- "missing runtime file for $variant: ${(qqq)pty_output}"
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
  print -u2 -r -- "timeout waiting for $variant: ${(qqq)pty_output}"
  return 1
}

print -r -- $'measured_at_utc\tbuild\tblock\tposition\tvariant\trepetition\tfirst_editable_ms' > $stage
local -a variants
variants=(baseline-clean baseline-external baseline-external-ready candidate-disabled candidate-clean candidate-external candidate-external-ready)
local variant repetition block position
for variant in $variants; do
  for repetition in {1..$warmups}; do
    measure_startup $variant warmup 0 $repetition 0
  done
done

local -a order
for block in forward reverse; do
  if [[ $block == forward ]]; then
    order=($variants)
  else
    order=(${(Oa)variants})
  fi
  position=0
  for variant in $order; do
    (( ++position ))
    for repetition in {1..$repetitions}; do
      measure_startup $variant $block $position $repetition 1
    done
  done
done

mv -- $stage $output
trap - EXIT INT TERM
command rm -rf -- $benchmark_root
print -r -- $output
