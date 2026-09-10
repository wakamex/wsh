#!/usr/bin/env zsh
builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
(( $# == 1 || $# == 2 )) || exit 2
readonly bundle=${1:A} omz=${2:-}
readonly scratch=$(mktemp -d /var/tmp/wsh-directory-jump.XXXXXX)
trap 'rm -rf -- $scratch' EXIT INT TERM
readonly home=$scratch/home state=$scratch/state
mkdir -p $home $scratch/bin "$scratch/project alpha" "$scratch/project beta" "$scratch/safe \$(touch owned)"
printf '#!/bin/sh\nprintf "external-z\\n"\n' > $scratch/bin/z
chmod +x $scratch/bin/z
python3 "${0:A:h:h}/build/native_manifest.py" verify $bundle >/dev/null
cp $bundle/share/wsh/defaults/zsh-z/z.plugin.zsh $scratch/modified.zsh
print -r -- '# local modification' >> $scratch/modified.zsh
cat > $home/.zshrc <<'CONFIG'
PROMPT='JUMP> '
autoload -Uz compinit
compinit -D
ZSHZ_DATA=$HOME/jump-data
case ${JUMP_CASE:-builtin} in
  external|legacy-completion|modified|override|custom-alias|custom-command|removed|disabled-external)
    if [[ $JUMP_CASE == custom-command ]]; then
      ZSHZ_CMD=j
      ZSHZ_CASE=ignore
      ZSHZ_COMPLETION=legacy
      ZSHZ_ECHO=1
      ZSHZ_DATA=$HOME/custom-database
    fi
    source "$JUMP_EXTERNAL"
    case $JUMP_CASE in
      legacy-completion) autoload -Uz _z ;;
      external)
        zshz --add "$JUMP_ROOT/project alpha"
        typeset -g JUMP_DATABASE_BEFORE=$(<$ZSHZ_DATA)
        ;;
      override) _zshz_chpwd() { ZSHZ[DIRECTORY_REMOVED]=0 } ;;
      custom-alias) alias z='print custom-alias' ;;
      disabled-external) WSH_DISABLE_DIRECTORY_JUMP=1 ;;
      removed)
        builtin cd "$JUMP_ROOT/project alpha"
        zshz --add "$PWD"
        zshz -x
        ;;
    esac
    ;;

  omz)
    ZSH=$JUMP_OMZ
    ZSH_THEME=""
    ZSH_CACHE_DIR=$HOME/cache
    ZSH_COMPDUMP=$HOME/.zcompdump
    ZSH_DISABLE_COMPFIX=true
    zstyle ':omz:update' mode disabled
    plugins=(z)
    source "$ZSH/oh-my-zsh.sh"
    ;;
  custom) z() { print -r -- custom-z; } ;;
  disabled) WSH_DISABLE_DIRECTORY_JUMP=1 ;;
esac
CONFIG
cat > $scratch/probe.zsh <<'PROBE'
builtin emulate -L zsh
case $JUMP_CASE in
  executable)
    [[ $WSH_DIRECTORY_JUMP_OWNER == external && $(z) == external-z ]] || return 1
    return
    ;;
  custom)
    [[ $WSH_DIRECTORY_JUMP_OWNER == external && $(z) == custom-z ]] || return 1
    return
    ;;
  disabled)
    [[ $WSH_DIRECTORY_JUMP_OWNER == disabled && ! -v functions[zshz] ]] || return 1
    return
    ;;
  modified|override|custom-alias|disabled-external)
    local expected_owner=external
    [[ $JUMP_CASE != disabled-external ]] || expected_owner=disabled
    [[ $WSH_DIRECTORY_JUMP_OWNER == $expected_owner ]] || return 1
    [[ $WSH_DIRECTORY_JUMP_REPLACED == 0 && $functions[zshz] != *wsh-directory* ]] || return 1
    [[ $JUMP_CASE != custom-alias || $aliases[z] == 'print custom-alias' ]] || return 1
    return
    ;;
  external|omz|legacy-completion|custom-command|removed)
    [[ $WSH_DIRECTORY_JUMP_OWNER == wsh && $WSH_DIRECTORY_JUMP_REPLACED == 1 ]] || return 1
    [[ $functions[zshz] == *wsh-directory* ]] || return 1
    ;;
  *) [[ $WSH_DIRECTORY_JUMP_OWNER == wsh && $_comps[z] == _zshz ]] || return 1 ;;
esac
if [[ $JUMP_CASE == external ]]; then
  [[ $(<$ZSHZ_DATA) == $JUMP_DATABASE_BEFORE ]] || return 1
fi
if [[ $JUMP_CASE == custom-command ]]; then
  [[ $ZSHZ_CMD == j && $aliases[j] == 'zshz 2>&1' && $ZSHZ_CASE == ignore && $ZSHZ_COMPLETION == legacy && $ZSHZ_ECHO == 1 && $ZSHZ_DATA == $HOME/custom-database ]] || return 1
fi
if [[ $JUMP_CASE == removed ]]; then
  [[ $ZSHZ[DIRECTORY_REMOVED] == 1 ]] || return 1
  _zshz_precmd
  [[ $(<$ZSHZ_DATA) != *"$PWD|"* ]] || return 1
  builtin cd "$JUMP_ROOT/project beta"
  [[ $ZSHZ[DIRECTORY_REMOVED] == 0 ]] || return 1
  builtin wsh-directory --can-record || return 1
fi
local -a hooks=("${(@M)precmd_functions:#_zshz_precmd}")
(( $#hooks == 1 )) || return 1
hooks=("${(@M)chpwd_functions:#_zshz_chpwd}")
(( $#hooks == 1 )) || return 1
zshz --add "$JUMP_ROOT/project alpha" || return 1
zshz --add "$JUMP_ROOT/project beta" || return 1
zshz --add "$JUMP_ROOT/project beta" || return 1
zshz -r project || return 1
[[ $PWD == "$JUMP_ROOT/project beta" ]] || return 1
zshz alpha || return 1
[[ $PWD == "$JUMP_ROOT/project alpha" ]] || return 1
if [[ $JUMP_CASE == custom-command ]]; then
  zshz ALPHA || return 1
  [[ $PWD == "$JUMP_ROOT/project alpha" ]] || return 1
fi
local before=$PWD
! zshz no-such-directory-unique || return 1
[[ $PWD == $before ]] || return 1
zshz --add "$JUMP_ROOT/safe \$(touch owned)" || return 1
zshz safe || return 1
[[ $PWD == "$JUMP_ROOT/safe \$(touch owned)" && ! -e owned ]] || return 1
[[ -s $ZSHZ_DATA ]] || return 1
[[ ! -e "$JUMP_ROOT/owned" && ! -e "$JUMP_ROOT/project alpha/owned" && ! -e "$JUMP_ROOT/project beta/owned" ]] || return 1
if [[ $WSH_DIRECTORY_JUMP_REPLACED == 1 ]]; then
  zsh-z_plugin_unload
  (( ! ${+functions[zshz]} && ! ${precmd_functions[(Ie)_zshz_precmd]:-0} && ! ${chpwd_functions[(Ie)_zshz_chpwd]:-0} )) || return 1
  builtin wsh-directory --can-record || return 1
fi
PROBE
variants=(builtin external legacy-completion modified override custom-alias custom-command removed disabled-external custom executable disabled)
[[ -n $omz ]] && variants+=(omz)
for variant in $variants; do
  effective_path=$PATH
  [[ $variant == executable ]] && effective_path=$scratch/bin:$PATH
  external_source=$bundle/share/wsh/defaults/zsh-z/z.plugin.zsh
  [[ $variant != modified ]] || external_source=$scratch/modified.zsh
  PATH=$effective_path HOME=$home ZDOTDIR=$home WSH_THEME= JUMP_CASE=$variant JUMP_ROOT=$scratch JUMP_OMZ=$omz \
  JUMP_EXTERNAL=$external_source JUMP_PROBE=$scratch/probe.zsh \
    $bundle/bin/wsh -d -dic '[[ $JUMP_CASE == removed ]] || cd "$JUMP_ROOT"; source "$JUMP_PROBE"' || exit 1
  print -r -- "PASS: $variant directory-jump ownership and behavior"
done
HOME=$home ZDOTDIR=$home WSH_THEME= JUMP_CASE=builtin JUMP_ROOT=$scratch \
  $bundle/bin/wsh -d -dic 'zshz beta; [[ $PWD == "$JUMP_ROOT/project beta" ]]'
print -r -- 'PASS: directory database persists across Wsh sessions'

# Exercise recording and completion through real ZLE, including a spaced path.
zmodload zsh/zpty zsh/datetime zsh/zselect
local output= pty=wsh_jump_${$}
cleanup() { zpty -d $pty 2>/dev/null || true; rm -rf -- $scratch; }
trap cleanup EXIT INT TERM
child() {
  export HOME=$home ZDOTDIR=$home TERM=xterm-256color JUMP_CASE=external JUMP_EXTERNAL=$bundle/share/wsh/defaults/zsh-z/z.plugin.zsh WSH_THEME=
  command stty -echo
  exec $bundle/bin/wsh -d
}
read_until() {
  local expected=$1 chunk
  local -F deadline=$(( EPOCHREALTIME + 8 ))
  while (( EPOCHREALTIME < deadline )); do
    while zpty -r -t $pty chunk 2>/dev/null; do output+=$chunk; done
    [[ $output == *$expected* ]] && return 0
    zselect -t 1 2>/dev/null || true
  done
  print -u2 -r -- "FAIL waiting for ${(qqq)expected}: ${(qqq)output}"
  return 1
}
zpty -b $pty child
read_until $'\e]133;B\e\\'
output=
zpty -w $pty $'z alpha\t'
read_until 'project'
zpty -w $pty "print -r -- \$'JUMP_\\x50WD:'\$PWD"
read_until "JUMP_PWD:$scratch/project alpha"
mkdir -p "$scratch/recorded visit"
output=
zpty -w $pty "cd ${(q)scratch}/'recorded visit'"
read_until $'\e]133;B\e\\'
local -F deadline=$(( EPOCHREALTIME + 5 ))
while (( EPOCHREALTIME < deadline )) && [[ $(<$home/jump-data) != *'/recorded visit|'* ]]; do
  zselect -t 1 2>/dev/null || true
done
[[ $(<$home/jump-data) == *'/recorded visit|'* ]]
zpty -w $pty exit
print -r -- 'PASS: real ZLE completion handles spaces and prompt hooks record directory visits'
