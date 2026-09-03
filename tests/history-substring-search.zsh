#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
zmodload zsh/datetime zsh/zpty zsh/zselect

(( $# == 2 || $# == 7 )) || {
  print -u2 -- 'usage: history-substring-search.zsh MANAGER BUNDLE [HSS-REPOSITORY OMZ-REPOSITORY AUTOSUGGESTIONS-REPOSITORY SYNTAX-HIGHLIGHTING-REPOSITORY baseline|candidate]'
  exit 2
}

readonly manager=${1:A}
readonly bundle=${2:A}
readonly hss_repository=${3:-}
readonly omz_repository=${4:-}
readonly autosuggestions_repository=${5:-}
readonly syntax_repository=${6:-}
readonly expectation=${7:-candidate}
readonly external_sources=$(( $# == 7 ))
readonly hss_revision=14c8d2e0ffaee98f2df9850b19944f32546fdea5
readonly omz_revision=9112b53fa8b5ab556c7c893aa8be8a247ac512a0
readonly autosuggestions_revision=85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5
readonly syntax_revision=2fc57d63067c18b1100ecdbf684fa5baf49459d1

[[ -x $manager && -x $bundle/bin/zsh && ( $expectation == baseline || $expectation == candidate ) ]] || {
  print -u2 -- 'error: manager, bundle, or expectation is invalid'
  exit 2
}
if (( external_sources )); then
  local repository revision
  for repository revision in \
    ${hss_repository:A} $hss_revision \
    ${omz_repository:A} $omz_revision \
    ${autosuggestions_repository:A} $autosuggestions_revision \
    ${syntax_repository:A} $syntax_revision; do
    git -C $repository cat-file -e ${revision}^{commit} 2>/dev/null || {
      print -u2 -- "error: required source revision is unavailable: ${revision}"
      exit 2
    }
  done
fi

readonly test_root=$(mktemp -d /var/tmp/wsh-history-correctness.XXXXXX)
readonly state_root=$test_root/state
readonly fixture=$test_root/fixture
readonly hss_source=$test_root/hss
readonly omz_source=$test_root/omz
readonly autosuggestions_source=$test_root/autosuggestions
readonly syntax_source=$test_root/syntax
typeset -g current_pty= pty_output= child_home= child_buffer_log= child_state_log=

cleanup() {
  [[ -z $current_pty ]] || zpty -d $current_pty 2>/dev/null || true
  command rm -rf -- $test_root
}
trap cleanup EXIT INT TERM

command mkdir -p -- $state_root $fixture $hss_source $omz_source $autosuggestions_source $syntax_source
if (( external_sources )); then
  git -C ${hss_repository:A} archive $hss_revision | tar -xf - -C $hss_source
  git -C ${omz_repository:A} archive $omz_revision | tar -xf - -C $omz_source
  git -C ${autosuggestions_repository:A} archive $autosuggestions_revision | tar -xf - -C $autosuggestions_source
  git -C ${syntax_repository:A} archive $syntax_revision | tar -xf - -C $syntax_source
else
  command cp -- $bundle/share/wsh/defaults/zsh-history-substring-search.zsh $hss_source/zsh-history-substring-search.zsh
  command mkdir -p -- $omz_source/plugins/history-substring-search
  command cp -- $bundle/share/wsh/defaults/known-oh-my-zsh-history-substring-search.zsh $omz_source/plugins/history-substring-search/history-substring-search.zsh
  print -r -- '0=${(%):-%N}
source ${0:A:h}/history-substring-search.zsh
zmodload zsh/terminfo
bindkey -M emacs "$terminfo[kcuu1]" history-substring-search-up
bindkey -M emacs "$terminfo[kcud1]" history-substring-search-down' >| $omz_source/plugins/history-substring-search/history-substring-search.plugin.zsh
fi
$manager bundle activate $bundle --state-root $state_root >/dev/null

git -C $fixture init -q -b main
git -C $fixture config user.name 'wsh history correctness test'
git -C $fixture config user.email history-correctness@wsh.invalid
print -r -- tracked > $fixture/tracked
git -C $fixture add tracked
git -C $fixture commit -qm initial

write_home() {
  local variant=$1
  local home=$test_root/home-$variant
  command mkdir -p -- $home
  local config=$home/.zshrc
  print -r -- 'setopt hist_ignore_space
print -s "print -r -- WSH_MATCH_OLDER"
print -s "print -r -- WSH_MATCH_NEWER"
_wsh_test_report_buffer() {
  print -r -- "$BUFFER" >> $WSH_TEST_BUFFER_LOG
  BUFFER=""
  zle .accept-line
}
_wsh_test_report_state() {
  zmodload zsh/parameter zsh/zleparameter
  local up_source=${functions_source[history-substring-search-up]:-none}
  local up_binding=$(bindkey -M emacs $'"'"'\eOA'"'"' 2>/dev/null)
  up_binding=${up_binding##* }
  local custom_binding=$(bindkey -M emacs $'"'"'\e[A'"'"' 2>/dev/null)
  custom_binding=${custom_binding##* }
  local pre_count=${#${(M)zle_line_pre_redraw_functions:#_history-substring-search-zle-line-pre-redraw}}
  local finish_count=${#${(M)zle_line_finish_functions:#_history-substring-search-zle-line-finish}}
  print -r -- "${WSH_HISTORY_SUBSTRING_SEARCH_OWNER-unset}|${WSH_HISTORY_SUBSTRING_SEARCH_REPLACED-unset}|${up_source}|${up_binding}|${custom_binding}|${pre_count}|${finish_count}|${HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND-unset}|${HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_NOT_FOUND-unset}|${HISTORY_SUBSTRING_SEARCH_GLOBBING_FLAGS-unset}|${HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE-unset}|${HISTORY_SUBSTRING_SEARCH_FUZZY-unset}|${HISTORY_SUBSTRING_SEARCH_PREFIXED-unset}|${HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_TIMEOUT-unset}" >> $WSH_TEST_STATE_LOG
  BUFFER=""
  zle .accept-line
}
zle -N _wsh_test_report_buffer
zle -N _wsh_test_report_state
bindkey -M emacs '^G' _wsh_test_report_buffer
bindkey -M emacs '^T' _wsh_test_report_state' >| $config

  case $variant in
    clean) ;;
    external-upstream)
      print -r -- "source ${(q)hss_source}/zsh-history-substring-search.zsh
bindkey -M emacs \$'\\eOA' history-substring-search-up
bindkey -M emacs \$'\\eOB' history-substring-search-down" >> $config
      ;;
    external-omz)
      print -r -- "source ${(q)omz_source}/plugins/history-substring-search/history-substring-search.plugin.zsh" >> $config
      ;;
    unknown)
      print -r -- '_wsh_unknown_up() { BUFFER=UNKNOWN_UP }
_wsh_unknown_down() { BUFFER=UNKNOWN_DOWN }
zle -N history-substring-search-up _wsh_unknown_up
zle -N history-substring-search-down _wsh_unknown_down
bindkey -M emacs $'"'"'\eOA'"'"' history-substring-search-up
bindkey -M emacs $'"'"'\eOB'"'"' history-substring-search-down' >> $config
      ;;
    custom-binding)
      print -r -- '_wsh_custom_up() { BUFFER=CUSTOM_UP }
zle -N _wsh_custom_up
bindkey -M emacs $'"'"'\eOA'"'"' _wsh_custom_up' >> $config
      ;;
    disabled)
      print -r -- 'typeset -g WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1' >> $config
      ;;
    configured)
      print -r -- 'typeset -g HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND=fg=blue
typeset -g HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_NOT_FOUND=fg=yellow
typeset -g HISTORY_SUBSTRING_SEARCH_GLOBBING_FLAGS=""
typeset -g HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE=1
typeset -g HISTORY_SUBSTRING_SEARCH_FUZZY=1
typeset -g HISTORY_SUBSTRING_SEARCH_PREFIXED=1
typeset -g HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_TIMEOUT=0.25' >> $config
      ;;
    composition)
      print -r -- "source ${(q)autosuggestions_source}/zsh-autosuggestions.zsh
source ${(q)hss_source}/zsh-history-substring-search.zsh
source ${(q)syntax_source}/zsh-syntax-highlighting.zsh" >> $config
      ;;
  esac
}

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

wait_for_lines() {
  local file=$1 expected=$2
  local -F deadline=$(( EPOCHREALTIME + 3 ))
  while (( EPOCHREALTIME < deadline )); do
    [[ -e $file && $(wc -l < $file) -ge $expected ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -- "timeout waiting for ${expected} lines in ${file}"
  return 1
}

managed_child() {
  builtin cd -q -- $fixture
  export HOME=$child_home
  export ZDOTDIR=$child_home
  export WSH_STATE_ROOT=$state_root
  export WSH_TEST_BUFFER_LOG=$child_buffer_log
  export WSH_TEST_STATE_LOG=$child_state_log
  export TERM=xterm-256color
  unset EDITOR VISUAL WSH_BUNDLE_ROOT WSH_USER_ZDOTDIR WSH_STARTUP_BUNDLE_ZDOTDIR WSH_STARTUP_RCS
  command stty -echo
  exec $manager run --state-root $state_root
}

start_variant() {
  local variant=$1
  child_home=$test_root/home-$variant
  child_buffer_log=$test_root/$variant-buffer.log
  child_state_log=$test_root/$variant-state.log
  : >| $child_buffer_log
  : >| $child_state_log
  current_pty=wsh_history_${variant//[^A-Za-z0-9]/_}_${$}
  pty_output=
  zpty -b $current_pty managed_child
  pty_wait_for_prompt
}

stop_variant() {
  zpty -w $current_pty exit
  zpty -d $current_pty 2>/dev/null || true
  current_pty=
}

report_state() {
  zpty -w -n $current_pty $'\x14'
  wait_for_lines $child_state_log 1
  print -r -- "$(<$child_state_log)"
}

assert_search() {
  local query=$1 keys=$2 expected=$3 line_number=$4
  zpty -w -n $current_pty $query
  zpty -w -n $current_pty $keys
  zpty -w -n $current_pty $'\x07'
  wait_for_lines $child_buffer_log $line_number
  local actual=$(sed -n "${line_number}p" $child_buffer_log)
  [[ $actual == $expected ]] || {
    print -u2 -r -- "unexpected search result ${line_number}: expected=${(qqq)expected} actual=${(qqq)actual}"
    return 1
  }
}

local -a variants
if [[ $expectation == baseline ]]; then
  variants=(clean external-upstream)
else
  variants=(clean external-upstream external-omz unknown custom-binding disabled configured)
  (( external_sources )) && variants+=(composition)
fi
local variant state
for variant in $variants; do
  write_home $variant
  start_variant $variant
  state=$(report_state)

  if [[ $expectation == baseline ]]; then
    case $variant in
      clean) [[ $state == unset\|unset\|none\|* ]] || { print -u2 -r -- "unexpected baseline clean state: $state"; exit 1; } ;;
      external-upstream)
        [[ $state == unset\|unset\|${hss_source}/zsh-history-substring-search.zsh\|history-substring-search-up\|* ]] || { print -u2 -r -- "unexpected baseline external state: $state"; exit 1; }
        assert_search wsh_match $'\eOA' 'print -r -- WSH_MATCH_NEWER' 1
        ;;
    esac
  else
    case $variant in
      clean)
        [[ $state == wsh\|0\|${bundle}/share/wsh/defaults/zsh-history-substring-search.zsh\|history-substring-search-up\|* ]] || { print -u2 -r -- "unexpected clean state: $state"; exit 1; }
        assert_search wsh_match $'\eOA' 'print -r -- WSH_MATCH_NEWER' 1
        assert_search wsh_match $'\eOA\eOA' 'print -r -- WSH_MATCH_OLDER' 2
        assert_search wsh_match $'\eOA\eOA\eOB' 'print -r -- WSH_MATCH_NEWER' 3
        assert_search WSH_NO_MATCH_UNIQUE $'\eOA' WSH_NO_MATCH_UNIQUE 4
        ;;
      external-upstream|external-omz)
        [[ $state == wsh\|1\|${bundle}/share/wsh/defaults/zsh-history-substring-search.zsh\|history-substring-search-up\|*\|0\|0\|* ]] || { print -u2 -r -- "unexpected recognized external state for ${variant}: $state"; exit 1; }
        assert_search wsh_match $'\eOA' 'print -r -- WSH_MATCH_NEWER' 1
        ;;
      unknown)
        [[ $state == external-unknown\|0\|none\|history-substring-search-up\|* ]] || { print -u2 -r -- "unexpected unknown implementation state: $state"; exit 1; }
        assert_search arbitrary $'\eOA' UNKNOWN_UP 1
        ;;
      custom-binding)
        [[ $state == wsh\|0\|${bundle}/share/wsh/defaults/zsh-history-substring-search.zsh\|_wsh_custom_up\|* ]] || { print -u2 -r -- "custom binding was not preserved: $state"; exit 1; }
        assert_search arbitrary $'\eOA' CUSTOM_UP 1
        ;;
      disabled)
        [[ $state == disabled\|0\|none\|* ]] || { print -u2 -r -- "unexpected disabled state: $state"; exit 1; }
        ;;
      configured)
        [[ $state == *'|fg=blue|fg=yellow||1|1|1|0.25' ]] || { print -u2 -r -- "configuration was not preserved: $state"; exit 1; }
        ;;
      composition)
        [[ $state == wsh\|1\|${bundle}/share/wsh/defaults/zsh-history-substring-search.zsh\|history-substring-search-up\|*\|0\|0\|* ]] || { print -u2 -r -- "unexpected composition state: $state"; exit 1; }
        assert_search wsh_match $'\eOA' 'print -r -- WSH_MATCH_NEWER' 1
        ;;
    esac
  fi
  stop_variant
done

print -r -- "PASS: history substring search ${expectation} behavior"
