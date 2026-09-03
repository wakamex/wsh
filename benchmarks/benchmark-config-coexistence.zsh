#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 7 )) || {
  print -u2 -- 'usage: benchmark-config-coexistence.zsh OUTPUT MANAGER BUNDLE OMZ WAKAMEX AUTOSUGGESTIONS SYNTAX-HIGHLIGHTING'
  exit 2
}

readonly output=${1:A}
readonly manager=${2:A}
readonly bundle=${3:A}
readonly omz_source=${4:A}
readonly wakamex_source=${5:A}
readonly autosuggestions_source=${6:A}
readonly syntax_highlighting_source=${7:A}
readonly omz_commit=9112b53fa8b5ab556c7c893aa8be8a247ac512a0
readonly wakamex_commit=15c7c78214774408a6c007d0401415c7d0cded38
readonly autosuggestions_commit=85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5
readonly syntax_highlighting_commit=2fc57d63067c18b1100ecdbf684fa5baf49459d1
readonly repetitions=20
readonly warmups=5
readonly cpu=${WSH_CONFIG_CPU:-0}

[[ ! -e $output && ! -L $output && -x $manager && -x $bundle/bin/zsh ]] || {
  print -u2 -- 'error: output must be new and manager and bundle must exist'
  exit 2
}

readonly scratch=$(mktemp -d /var/tmp/wsh-config-benchmark.XXXXXX)
readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
readonly omz=$scratch/omz
readonly state_root=$scratch/state
readonly fixture=$scratch/fixture
readonly direct_zdotdir=$scratch/direct-zdotdir
typeset -g current_pty= pty_output= current_home= current_variant=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $scratch $stage
}
trap cleanup EXIT INT TERM

command mkdir -p -- $omz $state_root $fixture $direct_zdotdir
git -C $omz_source archive $omz_commit | tar -xf - -C $omz
command mkdir -p -- $omz/custom/plugins/zsh-autosuggestions $omz/custom/plugins/zsh-syntax-highlighting $omz/custom/themes
git -C $autosuggestions_source archive $autosuggestions_commit | tar -xf - -C $omz/custom/plugins/zsh-autosuggestions
git -C $syntax_highlighting_source archive $syntax_highlighting_commit | tar -xf - -C $omz/custom/plugins/zsh-syntax-highlighting
git -C $wakamex_source archive $wakamex_commit | tar -xf - -C $omz/custom/themes
$manager bundle activate $bundle --state-root $state_root >/dev/null
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh coexistence benchmark'
git -C $fixture config user.email coexistence@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial

local variant theme plugin_list home
for variant in empty plain omz-none robbyrussell agnoster wakamex plugins wakamex-plugins; do
  home=$scratch/home-$variant
  command mkdir -p -- $home
  [[ $variant == empty ]] && continue
  if [[ $variant == plain ]]; then
    print -r -- "alias wsh_config_probe='print -r -- WSH_CONFIG_ALIAS_OK'" > $home/.zshrc
    continue
  fi
  theme=
  plugin_list=
  case $variant in
    robbyrussell|agnoster) theme=$variant ;;
    wakamex) theme=wakamex ;;
    plugins) plugin_list='history-substring-search zsh-autosuggestions zsh-syntax-highlighting' ;;
    wakamex-plugins)
      theme=wakamex
      plugin_list='history-substring-search zsh-autosuggestions zsh-syntax-highlighting'
      ;;
  esac
  print -r -- "export ZSH=${(q)omz}
ZSH_THEME=${(q)theme}
plugins=(${plugin_list})
ZSH_COMPDUMP=${(q)home}/.zcompdump
ZSH_CACHE_DIR=${(q)home}/cache
DISABLE_AUTO_UPDATE=true
DISABLE_AUTO_TITLE=true
ZSH_DISABLE_COMPFIX=true
zstyle ':omz:update' mode disabled
source \$ZSH/oh-my-zsh.sh" > $home/.zshrc
done

print -r -- "module_path=(${(q)bundle}/lib/zsh/5.9.2)
fpath=(${(q)bundle}/share/zsh/5.9.2/functions \$fpath)
source ${(q)scratch}/home-plain/.zshrc
source ${(q)bundle}/share/wsh/integration.zsh" > $direct_zdotdir/.zshrc

pty_read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

startup_child() {
  builtin cd -q -- $fixture
  export HOME=$current_home
  export TERM=xterm-256color
  command stty -echo
  if [[ $current_variant == plain-direct ]]; then
    export ZDOTDIR=$direct_zdotdir
    export WSH_BUNDLE_ROOT=$bundle
    export WSH_RUNTIME=$bundle/bin/wsh-runtime
    export WSH_THEME=$bundle/share/wsh/themes/minimal.toml
    exec taskset -c $cpu $bundle/bin/zsh -d
  fi
  export ZDOTDIR=$current_home
  export WSH_STATE_ROOT=$state_root
  unset WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  exec taskset -c $cpu $manager run --state-root $state_root
}

measure_startup() {
  local variant=$1 block=$2 position=$3 repetition=$4
  current_variant=$variant
  current_home=$scratch/home-$variant
  [[ $variant == plain-direct ]] && current_home=$scratch/home-plain
  current_pty=wsh_config_startup_${$}_${block}_${position}_${repetition}
  pty_output=
  local -F started=$EPOCHREALTIME deadline elapsed_ms
  zpty -b $current_pty startup_child
  local pty_fd=$REPLY
  deadline=$(( started + 8 ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    if [[ $pty_output == *'% '* ]]; then
      elapsed_ms=$(( (EPOCHREALTIME - started) * 1000 ))
      printf '%s\t%s\t%d\t%s\t%d\t%.6f\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $block $position $variant $repetition $elapsed_ms >> $stage
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

print -r -- $'measured_at_utc\tblock\tposition\tvariant\trepetition\tfirst_editable_ms' > $stage
local -a variants=(plain-direct empty plain omz-none robbyrussell agnoster wakamex plugins wakamex-plugins)
local repetition block position
for variant in $variants; do
  for repetition in {1..$warmups}; do
    measure_startup $variant warmup 0 $repetition
  done
done
sed -i '/\twarmup\t/d' $stage

local -a order
for block in forward reverse; do
  if [[ $block == forward ]]; then
    order=($variants)
  else
    order=(wakamex-plugins plugins wakamex agnoster robbyrussell omz-none plain empty plain-direct)
  fi
  position=0
  for variant in $order; do
    (( ++position ))
    for repetition in {1..$repetitions}; do
      measure_startup $variant $block $position $repetition
    done
  done
done

mv -- $stage $output
trap - EXIT INT TERM
command rm -rf -- $scratch
print -r -- $output
