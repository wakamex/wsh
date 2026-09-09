################################################################################
# Zsh-z - jump around with Zsh - A native Zsh version of rupa/z without awk,
# sort, date, or sed
#
# https://github.com/agkozak/zsh-z
#
# Copyright (c) 2018-2026 Alexandros Kozak
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Zsh-z maintains a jump-list of the directories you actually use.
#
# INSTALL:
#   * put something like this in your .zshrc:
#       source /path/to/zsh-z.plugin.zsh
#   * cd around for a while to build up the database
#
# USAGE:
#   * z foo       cd to the most frecent directory matching foo
#   * z foo bar   cd to the most frecent directory matching both foo and bar
#                   (e.g. /foo/bat/bar/quux)
#   * z -r foo    cd to the highest ranked directory matching foo
#   * z -t foo    cd to most recently accessed directory matching foo
#   * z -l foo    List matches instead of changing directories
#   * z -e foo    Echo the best match without changing directories
#   * z -c foo    Restrict matches to subdirectories of PWD
#   * z -x        Remove a directory (default: PWD) from the database
#   * z -xR       Remove a directory (default: PWD) and its subdirectories from
#                   the database
#
# ENVIRONMENT VARIABLES:
#
#   ZSHZ_CASE -> if `ignore', pattern matching is case-insensitive; if `smart',
#     pattern matching is case-insensitive only when the pattern is all
#     lowercase
#   ZSHZ_CD -> the directory-changing command that is used (default: builtin cd)
#   ZSHZ_CMD -> name of command (default: z)
#   ZSHZ_COMPLETION -> completion method (default: 'frecent'; 'legacy' for
#     alphabetic sorting)
#   ZSHZ_DATA -> name of datafile (default: ~/.z)
#   ZSHZ_DEBUG -> if set, turn on debugging aids: WARN_CREATE_GLOBAL while the
#     command runs and per-function warnings (functions -W) at load time
#     (default: unset)
#   ZSHZ_ECHO -> if 1, print the directory name after jumping to it (default: 0)
#   ZSHZ_EXCLUDE_DIRS -> array of directories to exclude from your database
#     (default: empty)
#   ZSHZ_KEEP_DIRS -> array of directories that should not be removed from the
#     database, even if they are not currently available (default: empty)
#   ZSHZ_LOCK_TIMEOUT -> seconds to wait for the lockfile before giving up
#     (default: 1)
#   ZSHZ_MAX_SCORE -> maximum combined score the database entries can have
#     before beginning to age (default: 9000)
#   ZSHZ_NO_RESOLVE_SYMLINKS -> '1' prevents symlink resolution
#   ZSHZ_OWNER -> your username (if you want use Zsh-z while using sudo -s)
#   ZSHZ_TILDE -> if 1, display ~ in place of the full $HOME path in output
#     (default: 0)
#   ZSHZ_TRAILING_SLASH -> if 1, a query ending in / matches at the end of a
#     directory path (default: 0)
#   ZSHZ_UNCOMMON -> if 1, do not jump to "common directories," but rather drop
#     subdirectories based on what the search string was (default: 0)
################################################################################

# Minimalistic solution to allow this plugin to keep running under sh/bash/ksh
# emulation while continuing to use Zsh-only syntax features. `emulate zsh -c'
# evaluates its argument as code, so the script's own path -- `${(%):-%N}' --
# must be `${(q)}'-quoted; otherwise an install directory containing spaces or
# other shell-special characters (common on Cygwin/MSYS2 and macOS, where a
# home directory can be "C:\Users\John Smith" or "/Users/John Smith") would be
# word-split and the plugin would silently fail to re-source.
if [[ -o KSH_ARRAYS || -o SH_WORD_SPLIT ]]; then
  emulate zsh -c "source ${(q)${(%):-%N}}"
  return $?
fi

autoload -Uz is-at-least

if ! is-at-least 4.3.11; then
  print "Zsh-z requires Zsh v4.3.11 or higher." >&2
  return 1 2> /dev/null || exit 1
fi

############################################################
# The help message
#
# Globals:
#   ZSHZ_CMD
############################################################
_zshz_usage() {
  print "Usage: ${ZSHZ_CMD:-${_Z_CMD:-z}} [OPTION]... [ARGUMENT]
Jump to a directory that you have visited frequently or recently, or a bit of both, based on the partial string ARGUMENT.

With no ARGUMENT, list the directory history in ascending rank.

  --add Add a directory to the database
  -c    Only match subdirectories of the current directory
  -e    Echo the best match without going to it
  -h    Display this help and exit
  -l    List all matches without going to them
  -r    Match by rank
  -t    Match by recent access
  -x    Remove a directory from the database (by default, the current directory)
  -xR   Remove a directory and its subdirectories from the database (by default, the current directory)" |
    fold -s -w $(( COLUMNS > 0 ? COLUMNS : 80 )) >&2
}

############################################################
# Canonicalize a path in the manner of `:A' -- normalize it
# lexically as `:a' does, then resolve symlinks -- without
# requiring any of the path to exist.
#
# `${x:A}' itself cannot be trusted with a missing path on
# Zsh 4.3.11: when the top-level component of $x does not
# exist (`/gone/sub'), the realpath machinery segfaults the
# shell (upstream bug, 4.3.11 only; deeper missing
# components are handled correctly on every version). So
# apply `:A' only to the deepest ancestor of the path that
# exists -- `:A' on an existing path is safe everywhere --
# and reattach the missing components verbatim. That
# reproduces `:A' exactly: `:A' resolves the symlinks in the
# existing prefix and carries the nonexistent tail
# unchanged, and the tail cannot contain live symlinks
# precisely because it does not exist. (A broken symlink
# stops the ancestor walk without being resolved -- `-e'
# fails on one -- which also matches `:A', which leaves
# broken symlinks unresolved.)
#
# Arguments:
#   $1 The path to canonicalize
#
# Returns the canonical path in $REPLY.
############################################################
_zshz_realpath() {
  local dir=${1:a}
  local -a tail

  # `:h' at its fixed point (`/', or `//' where the OS treats that as
  # distinct) can climb no higher; if even that much of the path does not
  # exist, settle for the lexical normalization rather than hand `:A'
  # something dangerous.
  while [[ ! -e $dir && $dir != "${dir:h}" ]]; do
    tail=( "${dir:t}" "${tail[@]}" )
    dir=${dir:h}
  done
  [[ -e $dir ]] && dir=${dir:A}

  # `typeset -g': REPLY belongs to the caller by design. A plain assignment
  # would trip WARN_NESTED_VAR under `ZSHZ_DEBUG', since _zshz_realpath is a
  # top-level function and thus one of the ones `functions -W' marks.
  if (( ${#tail} )); then
    typeset -g REPLY=${dir%/}/${(j:/:)tail}
  else
    typeset -g REPLY=$dir
  fi
}

# Load zsh/datetime module, if necessary
(( ${+EPOCHSECONDS} )) || zmodload zsh/datetime

# Global associative array for internal use
typeset -gA ZSHZ

# Fallback utilities in case Zsh lacks zsh/files (as is the case with MobaXterm)
ZSHZ[CHMOD]='chmod'
ZSHZ[CHOWN]='chown'
ZSHZ[MV]='mv'
ZSHZ[RM]='rm'

# Try to load zsh/files. zf_chown, zf_mv, and zf_rm are usually present in Zsh
# 4.3.11. zf_chmod only became available in Zsh 5.0, so we load it separately
# below. If zsh/files is not available at all, we silently fall back to the
# external utilities chmod, chown, mv, and rm.
if [[ ${builtins[zf_chown]-} != 'defined' ||
      ${builtins[zf_mv]-}    != 'defined' ||
      ${builtins[zf_rm]-}    != 'defined' ]]; then
  zmodload -F zsh/files b:zf_chown b:zf_mv b:zf_rm &> /dev/null
fi

[[ ${builtins[zf_chmod]-} == 'defined' ]] ||
    zmodload -F zsh/files b:zf_chmod &> /dev/null

# Use zsh/files, if it is available.
[[ ${builtins[zf_chmod]-} == 'defined' ]] && ZSHZ[CHMOD]='zf_chmod'
[[ ${builtins[zf_chown]-} == 'defined' ]] && ZSHZ[CHOWN]='zf_chown'
[[ ${builtins[zf_mv]-} == 'defined' ]] && ZSHZ[MV]='zf_mv'
[[ ${builtins[zf_rm]-} == 'defined' ]] && ZSHZ[RM]='zf_rm'

# Load zsh/system, if necessary
[[ ${modules[zsh/system]-} == 'loaded' ]] || zmodload zsh/system &> /dev/null

# Make sure ZSHZ_EXCLUDE_DIRS has been declared so that other scripts can
# simply append to it
(( ${+ZSHZ_EXCLUDE_DIRS} )) || typeset -gUa ZSHZ_EXCLUDE_DIRS

# Determine if zsystem flock is available
zsystem supports flock &> /dev/null && ZSHZ[USE_FLOCK]=1

# Windows only: how many times to retry a datafile rename that fails.
#
# On Cygwin and MSYS2, rename() fails with EBUSY or EACCES whenever another
# process holds the tempfile or the datafile open without FILE_SHARE_DELETE --
# which is precisely what a virus scanner or the search indexer does to a file
# in the moments after it is created. Since the write path below creates the
# tempfile and renames it over the datafile microseconds later, that window is
# wide open. The rename's stderr is discarded there, so a scan that lands in
# the window silently loses an `--add' or a `-x': no message, no delay, just a
# directory that never made it into the database. The condition clears in
# milliseconds, so make a few more attempts before giving up.
#
# Everywhere else a failed rename means something real -- ENOSPC, EPERM, a
# cross-device move -- that retrying cannot fix and would only add latency to,
# so ZSHZ[MV_RETRIES] stays unset and the loops below make a single attempt,
# exactly as before.
#
# zsh/zselect provides the sub-second delay between attempts without forking
# /bin/sleep, whose fractional-seconds support is not portable in any case.
# MobaXterm's cut-down Cygwin does not ship zsh/zselect, so there
# ZSHZ[MV_RETRY_DELAY] stays unset and the retries happen back to back -- still
# worth making, since the scanner's handle is often gone by the next attempt.
#
# Four retries at 50ms is deliberately modest rather than generous. The rename
# runs while the lockfile is held, so every millisecond spent retrying is a
# millisecond other writers spend waiting, and they give up after
# ZSHZ_LOCK_TIMEOUT (1s by default) -- silently, since their adds are
# best-effort too. A budget that outlasts a large fraction of that timeout
# would trade one process's lost write for several others'. Measured on MSYS2
# against a handle held open with FILE_SHARE_READ, this recovers renames
# blocked for up to ~0.3s, comfortably more than a scan of a file this small
# takes.
if [[ $OSTYPE == (cygwin|msys) ]]; then
  ZSHZ[MV_RETRIES]=4
  [[ ${modules[zsh/zselect]-} == 'loaded' ]] || zmodload zsh/zselect &> /dev/null
  # In hundredths of a second, per `zselect -t'
  [[ ${builtins[zselect]-} == 'defined' ]] && ZSHZ[MV_RETRY_DELAY]=5
fi

############################################################
# The Zsh-z Command
#
# Globals:
#   ZSHZ
#   ZSHZ_CASE
#   ZSHZ_CD
#   ZSHZ_COMPLETION
#   ZSHZ_DATA
#   ZSHZ_DEBUG
#   ZSHZ_EXCLUDE_DIRS
#   ZSHZ_KEEP_DIRS
#   ZSHZ_LOCK_TIMEOUT
#   ZSHZ_MAX_SCORE
#   ZSHZ_OWNER
#
# Arguments:
#   $* Command options and arguments
############################################################
zshz() {
  setopt LOCAL_OPTIONS NO_KSH_ARRAYS NO_SH_WORD_SPLIT NO_EXTENDED_GLOB UNSET
  local REPLY result
  wsh-directory "$@"
  result=$?
  (( result == 64 )) && { _zshz_usage; return; }
  # Root removal is deliberately unavailable until confirmation parity passes.
  (( result == 65 )) && return 1
  (( result )) && return $result
  if [[ -n $REPLY ]]; then
    if [[ -z $ZSHZ_CD ]]; then
      builtin cd "$REPLY" || return
    else
      ${=ZSHZ_CD} "$REPLY" || return
    fi
    if (( ZSHZ_ECHO )); then
      if (( ZSHZ_TILDE )); then
        print -r -- ${PWD/#${HOME}/\~}
      else
        print -r -- $PWD
      fi
    fi
  fi
  return 0
}

alias ${ZSHZ_CMD:-${_Z_CMD:-z}}='zshz 2>&1'

############################################################
# precmd - add path to datafile unless `z -x' has just been
#   run
#
# Globals:
#   ZSHZ
############################################################
_zshz_precmd() {
  # Protect against `setopt NO_UNSET'
  setopt LOCAL_OPTIONS UNSET

  # Do not add PWD to datafile when in HOME directory, or
  # if `z -x' has just been run
  [[ $PWD == "$HOME" ]] || (( ZSHZ[DIRECTORY_REMOVED] )) && return

  # Don't track directory trees excluded in ZSHZ_EXCLUDE_DIRS
  local exclude
  for exclude in ${(@)ZSHZ_EXCLUDE_DIRS:-${(@)_Z_EXCLUDE_DIRS}}; do
    case $PWD in
      ${exclude}|${exclude}/*) return ;;
    esac
  done

  # Add PWD to the datafile. Background the write so the prompt doesn't wait on
  # read + tempfile + rename + chown -- which is tens of ms per prompt on
  # 9P-bridged or VHD-backed paths. Backgrounding is safe under develop's
  # lock design: the `always { zsystem flock -u $lockfd }' block in
  # _zshz_add_or_remove_path guarantees the parent never holds an open
  # lockfd between precmd invocations (so a `&!' fork can't inherit one),
  # and ZSHZ_LOCK_TIMEOUT (default 1s) bounds contention so a stuck holder
  # can't pile up writers. `&!' is zsh background + disown: no wrapper
  # subshell, no job-table entry, no "Done" line at the next prompt.
  #
  # Do not restore the old foreground carve-out for Cygwin/MSYS2. It was
  # right when backgrounding meant a subshell plus a job (two forks) and
  # writes were line-by-line; with one disowned fork and batched writes,
  # measurement (June 2026, Cygwin zsh 5.8 and MSYS2 zsh 5.9) shows ~10-12ms
  # at the prompt for `&!' vs. ~30ms for a foreground add at 300 datafile
  # entries -- and ~300ms at 1,000 entries, since the foreground cost grows
  # with the datafile while the fork cost stays flat.
  #
  # `2> /dev/null' is what actually enforces the "stay quiet at every prompt"
  # rule that $_zshz_quiet_add describes. That marker can only gate Zsh-z's own
  # `print's; it cannot reach the external and builtin commands further down the
  # --add path -- `mkdir -p', `id -ng', ${ZSHZ[CHOWN]}, the deliberately loud
  # datafile-creation retry, or Zsh's own redirection diagnostics -- and any of
  # those can fail when $ZSHZ_DATA sits on an unwritable or unmounted directory,
  # or when $ZSHZ_OWNER names a user `id' can't resolve. Suppressing at the fork
  # covers every such site at once, including ones added later, whereas
  # suppressing site by site has to be kept in sync forever. Nothing actionable
  # is lost: a foreground `z --add .' still reports in full, which is exactly
  # the diagnostic the lock comment above tells the user to run.
  local _zshz_quiet_add=1
  zshz --add "$PWD" 2> /dev/null &!

  # See https://github.com/rupa/z/pull/247/commits/081406117ea42ccb8d159f7630cfc7658db054b6
  : $RANDOM
}

############################################################
# chpwd
#
# When the $PWD is removed from the datafile with `z -x',
# Zsh-z refrains from adding it again until the user has
# left the directory.
#
# Globals:
#   ZSHZ
############################################################
_zshz_chpwd() {
  ZSHZ[DIRECTORY_REMOVED]=0
}

autoload -Uz add-zsh-hook

add-zsh-hook precmd _zshz_precmd
add-zsh-hook chpwd _zshz_chpwd

############################################################
# Completion
############################################################

# Standardized $0 handling
# https://zdharma-continuum.github.io/Zsh-100-Commits-Club/Zsh-Plugin-Standard.html
0="${${ZERO:-${0:#${ZSH_ARGZERO-}}}:-${(%):-%N}}"
0="${${(M)0:#/*}:-$PWD/$0}"

# Capture the plugin directory while $0 still names this file: inside the
# unload function, $0 is the function name (FUNCTION_ARGZERO), which `:A'
# would resolve against $PWD.
ZSHZ[PLUGIN_DIR]=${0:A:h}

# Add the plugin directory to $fpath only when nothing else has already put it
# there, and record having done so, so that unload can take back this entry
# and leave a plugin manager's alone.
#
# The record is only ever set, never cleared: on a re-source the directory is
# already present -- because this file added it the first time -- and clearing
# the record then would strand the entry in $fpath at unload. `typeset -gA'
# above preserves the value across that re-source.
if (( ${fpath[(ie)${ZSHZ[PLUGIN_DIR]}]} > ${#fpath} )); then
  fpath=( "${ZSHZ[PLUGIN_DIR]}" "${fpath[@]}" )
  # Record the path itself, not a boolean. $ZSHZ[PLUGIN_DIR] is rewritten by
  # every source, so a flag would end up describing whichever directory was
  # sourced last: re-sourcing from a second, manager-owned installation would
  # make unload drop *that* entry and strand the one this plugin actually
  # added. Newline-separated, since a path may contain spaces, and split with
  # `${(f)...}' at unload.
  ZSHZ[ADDED_FPATH]="${ZSHZ[ADDED_FPATH]:+${ZSHZ[ADDED_FPATH]}
}${ZSHZ[PLUGIN_DIR]}"
fi

# Save the existing Tab binding so that the completion widget can invoke it,
# but being careful not to create a situation where the widget ends up calling
# itself and causing infinite recursion if this script is re-sourced.
if (( ! ${+widgets[_zshz_zle_completion_widget]} )); then
  ZSHZ[TAB_BINDING]="${$(bindkey -M main '^I')##* }"
fi

############################################################
# ZLE widget to fix spaces-as-wildcards completion
#
# When completing a Zsh-z command with multiple search terms
# (e.g. `z us lo bi'), collapse the terms into a single
# wildcard-joined word (e.g. `z us*lo*bi') before triggering
# completion. This causes compadd to replace the whole query
# with the matched path rather than just the last word.
#
# Globals:
#   ZSHZ_CMD
############################################################
_zshz_zle_completion_widget() {

  setopt LOCAL_OPTIONS EXTENDED_GLOB NO_KSH_ARRAYS NO_SH_WORD_SPLIT

  local cmd=${ZSHZ_CMD:-${_Z_CMD:-z}}

  # Ensure tab completion works under `setopt COMPLETE_ALIASES'. Under that
  # option zsh looks up `_comps[$cmd]' verbatim rather than expanding the
  # alias to `zshz' first; compinit's static `#compdef' tag in `_zshz' is
  # parsed literally (no parameter expansion) and only covers the literal
  # `zshz' command. Run once -- the guard short-circuits on subsequent Tabs.
  # Record what was registered, so `zsh-z_plugin_unload' can take back exactly
  # this entry and nothing else. Keyed on the effect rather than compdef's exit
  # status: if the mapping did not land, there is nothing to take back.
  if (( ! ${+_comps[$cmd]} )); then
    compdef _zshz $cmd 2> /dev/null
    # Append rather than overwrite. Re-sourcing with a changed $ZSHZ_CMD
    # registers a second command while the first mapping is still live, and a
    # single slot would forget the earlier one and strand it at unload. Space-
    # separated, like $ZSHZ[FUNCTIONS], and split with `${=...}' there.
    [[ ${_comps[$cmd]-} == '_zshz' ]] &&
      ZSHZ[COMPDEF]="${ZSHZ[COMPDEF]:+${ZSHZ[COMPDEF]} }$cmd"
  fi

  # If a trailing space was added after an already-completed absolute path
  # (e.g. `z /usr/local/bin '), a second Tab would otherwise re-trigger
  # completion on an empty word and insert a duplicate. Bail out early.
  if [[ $LBUFFER[-1] == ' ' && ${${LBUFFER% }##* } == [/~]* ]]; then
    return
  fi

  # Only act when there are at least two words after the command
  if [[ $LBUFFER == ${cmd}\ *\ * ]]; then
    local after=${LBUFFER#${cmd} }
    local -a parts option_parts search_parts
    local p past_options=0

    parts=( ${(z)after} )
    for p in $parts; do
      if (( ! past_options )) && [[ $p == (--|-[cehlrRtx]##|--add|--complete|--help) ]]; then
        option_parts+=( $p )
        # `--' terminates option parsing; subsequent tokens are positional,
        # even if they happen to look like options.
        [[ $p == -- ]] && past_options=1
      else
        past_options=1
        search_parts+=( $p )
      fi
    done

    if (( ${#search_parts} > 1 )); then
      LBUFFER="${cmd}${option_parts:+ ${(j: :)option_parts}} ${(j:*:)search_parts}"
    fi
  fi

  # If Tab had a non-default binding, continue to use it; otherwise the default
  # expand-or-complete gets used.
  zle ${ZSHZ[TAB_BINDING]:-expand-or-complete}
}

# Register the widget and bind to Tab, but only if this script has not already
# been sourced -- avoid infinite recursion.
if (( ! ${+widgets[_zshz_zle_completion_widget]} )); then
  zle -N _zshz_zle_completion_widget
  bindkey -M main '^I' _zshz_zle_completion_widget
fi

############################################################
# zsh-z functions
############################################################
ZSHZ[FUNCTIONS]='_zshz_usage
                 _zshz_realpath
                 _zshz_add_or_remove_path
                 _zshz_update_datafile
                 _zshz_legacy_complete
                 _zshz_find_common_root
                 _zshz_output
                 _zshz_find_matches
                 zshz_cd
                 _zshz_echo
                 zshz
                 _zshz_precmd
                 _zshz_chpwd
                 _zshz
                 _zshz_zle_completion_widget'

############################################################
# Enable WARN_NESTED_VAR for functions listed in
#   ZSHZ[FUNCTIONS]
############################################################
(( ${+ZSHZ_DEBUG} )) && () {
  if is-at-least 5.4.0; then
    local x
    for x in ${=ZSHZ[FUNCTIONS]}; do
      functions -W $x
    done
  fi
}

############################################################
# Unload function
#
# See https://github.com/agkozak/Zsh-100-Commits-Club/blob/master/Zsh-Plugin-Standard.adoc#unload-fun
#
# Globals:
#   ZSHZ
#   ZSHZ_CMD
############################################################
zsh-z_plugin_unload() {
  emulate -L zsh

  add-zsh-hook -D precmd _zshz_precmd
  add-zsh-hook -d chpwd _zshz_chpwd

  zle -D _zshz_zle_completion_widget

  # Only restore Tab binding if it is still bound to our widget; otherwise
  # leave it alone.
  local _zshz_current_tab
  _zshz_current_tab="$(bindkey -M main '^I' 2>/dev/null || true)"
  if [[ ${_zshz_current_tab##* } == _zshz_zle_completion_widget ]]; then
    bindkey -M main '^I' "${ZSHZ[TAB_BINDING]:-expand-or-complete}"
  fi

  local x
  for x in ${=ZSHZ[FUNCTIONS]}; do
    (( ${+functions[$x]} )) && unfunction $x
  done

  # The directory captured at source time -- $0 here is the function name,
  # not the plugin file. Read it before ZSHZ is unset.
  #
  # Only when this plugin was the one that added it. A plugin manager that put
  # the directory on $fpath owns that entry: taking it away would break
  # autoloads for anything else living there and leave the manager believing
  # its configuration is intact. And drop a single occurrence rather than
  # filtering every match -- at most one of any duplicates can be ours.
  #
  # `(ie)', not `(i)': without the `e' the subscript treats the stored path as
  # a *pattern*, so a plugin directory containing `[', `*' or `?' would not
  # match itself and the entry would be left behind. The source-time lookup
  # already uses `(ie)'; these two must agree.
  local _zshz_dir
  integer _zshz_fp
  for _zshz_dir in ${(f)ZSHZ[ADDED_FPATH]-}; do
    [[ -n $_zshz_dir ]] || continue
    _zshz_fp=${fpath[(ie)$_zshz_dir]}
    (( _zshz_fp <= ${#fpath} )) && fpath[$_zshz_fp]=()
  done

  # Take back the completion mapping the widget installed on its first Tab.
  # Without this the entry outlives the function it names -- `_zshz' is
  # unfunctioned above and the plugin directory has just left $fpath, so a
  # later completion on that command looks up something unloadable.
  #
  # Only this one entry. compinit's own registrations (`_comps[zshz]', from the
  # static `#compdef' tag) are deliberately left in place: nothing re-runs
  # compinit when the plugin is sourced again, so removing them would break
  # completion for the literal `zshz' command until the user re-ran it by hand.
  # This entry has no such problem -- the widget re-registers it on the next
  # Tab after a reload.
  #
  # `$ZSHZ[COMPDEF]' is the ownership record: the registration above never
  # overwrites an existing mapping, so one Zsh-z did not create must survive
  # unload. Re-check the value too, in case it was repointed since.
  local _zshz_compdef
  for _zshz_compdef in ${=ZSHZ[COMPDEF]-}; do
    [[ ${_comps[$_zshz_compdef]-} == '_zshz' ]] &&
      compdef -d "$_zshz_compdef" 2> /dev/null
  done

  unset ZSHZ

  (( ${+aliases[${ZSHZ_CMD:-${_Z_CMD:-z}}]} )) &&
    unalias ${ZSHZ_CMD:-${_Z_CMD:-z}}

  unfunction $0
}

# vim: fdm=indent:ts=2:et:sts=2:sw=2:
