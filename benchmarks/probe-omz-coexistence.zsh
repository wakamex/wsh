#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 7 )) || {
  print -u2 -- 'usage: probe-omz-coexistence.zsh OUTPUT MANAGER BUNDLE OMZ WAKAMEX AUTOSUGGESTIONS SYNTAX-HIGHLIGHTING'
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

[[ ! -e $output && ! -L $output && -x $manager && -x $bundle/bin/zsh ]] || {
  print -u2 -- 'error: output must be new and manager and bundle must exist'
  exit 2
}
for source_pair in \
  $omz_source:$omz_commit \
  $wakamex_source:$wakamex_commit \
  $autosuggestions_source:$autosuggestions_commit \
  $syntax_highlighting_source:$syntax_highlighting_commit; do
  source_dir=${source_pair%%:*}
  source_commit=${source_pair##*:}
  git -C $source_dir cat-file -e ${source_commit}^{commit} 2>/dev/null || {
    print -u2 -- "error: missing source commit $source_commit in $source_dir"
    exit 2
  }
done

readonly scratch=$(mktemp -d /var/tmp/wsh-omz-coexistence.XXXXXX)
readonly stage=$(mktemp "${output:h}/.${output:t}.XXXXXX")
readonly omz=$scratch/omz
readonly state_root=$scratch/state
readonly fixture=$scratch/fixture
readonly probe_bin=$scratch/probe-bin
readonly git_log=$scratch/git.log
readonly real_git=${commands[git]:A}
typeset -g current_pty= pty_output= current_home=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $scratch $stage
}
trap cleanup EXIT INT TERM

command mkdir -p -- $omz $state_root $fixture $probe_bin
git -C $omz_source archive $omz_commit | tar -xf - -C $omz
command mkdir -p -- $omz/custom/plugins/zsh-autosuggestions $omz/custom/plugins/zsh-syntax-highlighting $omz/custom/themes
git -C $autosuggestions_source archive $autosuggestions_commit | tar -xf - -C $omz/custom/plugins/zsh-autosuggestions
git -C $syntax_highlighting_source archive $syntax_highlighting_commit | tar -xf - -C $omz/custom/plugins/zsh-syntax-highlighting
git -C $wakamex_source archive $wakamex_commit | tar -xf - -C $omz/custom/themes
$manager bundle activate $bundle --state-root $state_root >/dev/null
git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh coexistence probe'
git -C $fixture config user.email coexistence@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial
print -r -- "#!/bin/sh
printf '%s\\n' git >> ${(q)git_log}
exec ${(q)real_git} \"\$@\"" > $probe_bin/git
chmod 755 $probe_bin/git

pty_read_available() {
  local chunk
  while zpty -r -t $current_pty chunk 2>/dev/null; do
    pty_output+=$chunk
  done
}

pty_wait_for() {
  local expected=$1
  local -F deadline=$(( EPOCHREALTIME + ${2:-8} ))
  while (( EPOCHREALTIME < deadline )); do
    pty_read_available
    [[ $pty_output == *$expected* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  pty_read_available
  print -u2 -r -- "timeout waiting for ${(qqq)expected}: ${(qqq)pty_output}"
  return 1
}

managed_child() {
  builtin cd -q -- $fixture
  export HOME=$current_home
  export ZDOTDIR=$current_home
  export WSH_STATE_ROOT=$state_root
  export TERM=xterm-256color
  export PATH=$probe_bin:$PATH
  unset WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  exec $manager run --state-root $state_root
}

print -r -- $'variant\tuser_config\talias\twsh_runtime\twsh_prompt_owner\tautosuggestions\tsyntax_highlighting\thistory_substring_search\twakamex_worker\ttrivial_prompt_git_calls\tprecmd_hooks\tpreexec_hooks\tzshexit_hooks' > $stage

local variant theme plugin_list expect_plugins expect_wakamex
for variant in omz-none robbyrussell agnoster wakamex plugins wakamex-plugins; do
  current_home=$scratch/home-$variant
  command mkdir -p -- $current_home
  theme=
  plugin_list=
  expect_plugins=0
  expect_wakamex=0
  case $variant in
    robbyrussell|agnoster) theme=$variant ;;
    wakamex) theme=wakamex; expect_wakamex=1 ;;
    plugins) plugin_list='history-substring-search zsh-autosuggestions zsh-syntax-highlighting'; expect_plugins=1 ;;
    wakamex-plugins)
      theme=wakamex
      plugin_list='history-substring-search zsh-autosuggestions zsh-syntax-highlighting'
      expect_plugins=1
      expect_wakamex=1
      ;;
  esac
  print -r -- "export ZSH=${(q)omz}
ZSH_THEME=${(q)theme}
plugins=(${plugin_list})
ZSH_COMPDUMP=${(q)current_home}/.zcompdump
ZSH_CACHE_DIR=${(q)current_home}/cache
DISABLE_AUTO_UPDATE=true
DISABLE_AUTO_TITLE=true
ZSH_DISABLE_COMPFIX=true
zstyle ':omz:update' mode disabled
source \$ZSH/oh-my-zsh.sh
alias wsh_config_probe='print -r -- WSH_OMZ_ALIAS_OK'
print -r -- WSH_OMZ_USER_CONFIG:${variant}" > $current_home/.zshrc

  current_pty=wsh_omz_${variant}_${$}
  pty_output=
  zpty -b $current_pty managed_child
  pty_wait_for WSH_OMZ_USER_CONFIG:${variant}
  pty_wait_for '% '
  local -F settle_deadline=$(( EPOCHREALTIME + 0.3 ))
  while (( EPOCHREALTIME < settle_deadline )); do
    zselect -t 1 2>/dev/null || true
    pty_read_available
  done
  : >| $git_log
  pty_output=
  zpty -w $current_pty ':'
  pty_wait_for 'git:main'
  settle_deadline=$(( EPOCHREALTIME + 0.3 ))
  while (( EPOCHREALTIME < settle_deadline )); do
    zselect -t 1 2>/dev/null || true
    pty_read_available
  done
  local trivial_git_calls=$(wc -l < $git_log)
  zpty -w $current_pty wsh_config_probe
  pty_wait_for WSH_OMZ_ALIAS_OK
  zpty -w $current_pty "zmodload zsh/zleparameter; [[ \$PROMPT == \$WSH_LAST_PROMPT ]]; typeset _wsh_prompt_owner=\$?; print -r -- \$'WSH_\\x4fMZ_STATE:'\${WSH_INTEGRATION_LOADED-unset}:\${WSH_RUNTIME_READY:-0}:\${_wsh_prompt_owner}:\$(( \$+functions[_zsh_autosuggest_start] )):\$(( \$+ZSH_HIGHLIGHT_VERSION )):\$(( \$+widgets[history-substring-search-up] )):\${_WAKAMEX_GIT_PID:--1}:\${(j:,:)precmd_functions}:\${(j:,:)preexec_functions}:\${(j:,:)zshexit_functions}"
  pty_wait_for WSH_OMZ_STATE:
  local state=${${pty_output##*WSH_OMZ_STATE:}%%$'\r\n'*}
  local -a fields=(${(s.:.)state})
  (( ${#fields} >= 10 )) || {
    print -u2 -r -- "invalid state for $variant: ${(qqq)state}"
    exit 1
  }
  [[ $fields[1] == 1 && $fields[2] == 1 && $fields[3] == 0 ]] || {
    print -u2 -r -- "wsh did not own the active prompt for $variant: ${(qqq)state}"
    exit 1
  }
  if (( expect_plugins )); then
    [[ $fields[4] == 1 && $fields[5] == 1 && $fields[6] == 1 ]] || {
      print -u2 -r -- "ZLE plugins did not load together for $variant: ${(qqq)state}"
      exit 1
    }
  fi
  if (( expect_wakamex )); then
    [[ ,$fields[8], == *,_wakamex_git_request,* && ,$fields[9], == *,_wakamex_prompt_preexec,* && ,$fields[10], == *,_wakamex_git_shutdown,* ]] || {
      print -u2 -r -- "Wakamex lifecycle was not registered for $variant: ${(qqq)state}"
      exit 1
    }
  fi
  local -a wsh_precmd=(${(M)${(s:,:)fields[8]}:#_wsh_runtime_precmd})
  local -a wsh_preexec=(${(M)${(s:,:)fields[9]}:#_wsh_runtime_preexec})
  local -a wsh_zshexit=(${(M)${(s:,:)fields[10]}:#_wsh_runtime_stop})
  (( ${#wsh_precmd} == 1 && ${#wsh_preexec} == 1 && ${#wsh_zshexit} == 1 )) || {
    print -u2 -r -- "wsh hooks were duplicated for $variant: ${(qqq)state}"
    exit 1
  }
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    $variant loaded loaded ready wsh $fields[4] $fields[5] $fields[6] $fields[7] $trivial_git_calls \
    ${(q)fields[8]} ${(q)fields[9]} ${(q)fields[10]} >> $stage
  zpty -w $current_pty exit
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
done

mv -- $stage $output
trap - EXIT INT TERM
command rm -rf -- $scratch
print -r -- $output
