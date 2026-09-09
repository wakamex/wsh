#!/usr/bin/env zsh
##############################################################################
#
# Copyright (c) 2009 Peter Stephenson
# Copyright (c) 2011 Guido van Steen
# Copyright (c) 2011 Suraj N. Kurapati
# Copyright (c) 2011 Sorin Ionescu
# Copyright (c) 2011 Vincent Guerci
# Copyright (c) 2016 Geza Lore
# Copyright (c) 2017 Bengt Brodersen
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#
#  * Neither the name of the FIZSH nor the names of its contributors
#    may be used to endorse or promote products derived from this
#    software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
##############################################################################

#-----------------------------------------------------------------------------
# declare global configuration variables
#-----------------------------------------------------------------------------

: ${HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND='bg=magenta,fg=white,bold'}
: ${HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_NOT_FOUND='bg=red,fg=white,bold'}
: ${HISTORY_SUBSTRING_SEARCH_GLOBBING_FLAGS='i'}
: ${HISTORY_SUBSTRING_SEARCH_ENSURE_UNIQUE=''}
: ${HISTORY_SUBSTRING_SEARCH_FUZZY=''}
: ${HISTORY_SUBSTRING_SEARCH_PREFIXED=''}

#-----------------------------------------------------------------------------
# declare internal global variables
#-----------------------------------------------------------------------------

typeset -g BUFFER MATCH MBEGIN MEND CURSOR
typeset -g _history_substring_search_refresh_display
typeset -g _history_substring_search_query_highlight
typeset -g _history_substring_search_result
typeset -g _history_substring_search_query
typeset -g -a _history_substring_search_query_parts
typeset -g -a _history_substring_search_raw_matches
typeset -g -i _history_substring_search_raw_match_index
typeset -g -a _history_substring_search_matches
typeset -g -i _history_substring_search_match_index
typeset -g -A _history_substring_search_unique_filter
typeset -g -i _history_substring_search_zsh_5_9

#-----------------------------------------------------------------------------
# the main ZLE widgets
#-----------------------------------------------------------------------------

history-substring-search-up() {
  _history-substring-search-begin

  _history-substring-search-up-history ||
  _history-substring-search-up-buffer ||
  _history-substring-search-up-search

  _history-substring-search-end
}

history-substring-search-down() {
  _history-substring-search-begin

  _history-substring-search-down-history ||
  _history-substring-search-down-buffer ||
  _history-substring-search-down-search

  _history-substring-search-end
}

zle -N history-substring-search-up
zle -N history-substring-search-down

#-----------------------------------------------------------------------------
# implementation details
#-----------------------------------------------------------------------------

zmodload -F zsh/parameter
autoload -Uz is-at-least

if is-at-least 5.9 $ZSH_VERSION; then
  _history_substring_search_zsh_5_9=1
fi

#
# We have to "override" some keys and widgets if the
# zsh-syntax-highlighting plugin has not been loaded:
#
# https://github.com/nicoulaj/zsh-syntax-highlighting
#
if [[ $+functions[_zsh_highlight] -eq 0 ]]; then
  #
  # Dummy implementation of _zsh_highlight() that
  # simply removes any existing highlights when the
  # user inserts printable characters into $BUFFER.
  #
  _zsh_highlight() {
    if [[ $KEYS == [[:print:]] ]]; then
      region_highlight=()
    fi
  }

  #
  # Check if $1 denotes the name of a callable function, i.e. it is fully
  # defined or it is marked for autoloading and autoloading it at the first
  # call to it will succeed. In particular, if $1 has been marked for
  # autoloading but is not available in $fpath, then it will return 1 (false).
  #
  # This is based on the zsh-syntax-highlighting plugin.
  #
  _history-substring-search-function-callable() {
    if (( ${+functions[$1]} )) && ! [[ "$functions[$1]" == *"builtin autoload -X"* ]]; then
      return 0 # already fully loaded
    else
      # "$1" is either an autoload stub, or not a function at all.
      # We expect 'autoload +X' to return non-zero if it fails to fully load
      # the function.
      ( autoload -U +X -- "$1" 2>/dev/null )
      return $?
    fi
  }

  #
  # The zsh-syntax-highlighting plugin uses zle-line-pre-redraw hook instead
  # of the legacy "bind all widgets" if 1) zsh has the memo= feature (added in
  # version 5.9) and 2) add-zle-hook-widget is available.
  #
  if [[ $_history_substring_search_zsh_5_9 -eq 1 ]] && _history-substring-search-function-callable add-zle-hook-widget; then
    #
    # The following code is based on the zsh-syntax-highlighting plugin.
    #
    autoload -U add-zle-hook-widget

    _history-substring-search-zle-line-finish() {
      #
      # Reset $WIDGET since the 'main' highlighter depends on it.
      #
      # Since $WIDGET is declared by zle as read-only in this function's scope,
      # a nested function is required in order to shadow its built-in value;
      # see "User-defined widgets" in zshall.
      #
      () {
        local -h -r WIDGET=zle-line-finish
        _zsh_highlight
      }
    }

    _history-substring-search-zle-line-pre-redraw() {
      #
      # If the zsh-syntax-highlighting plugin has been loaded (after our plugin
      # plugin, otherwise this hook wouldn't be called), remove our hooks.
      #
      if [[ $+ZSH_HIGHLIGHT_VERSION -eq 1 ]]; then
        autoload -U add-zle-hook-widget
        add-zle-hook-widget -d zle-line-pre-redraw _history-substring-search-zle-line-pre-redraw
        add-zle-hook-widget -d zle-line-finish _history-substring-search-zle-line-finish
        return 0
      fi
      #
      # Set $? to 0 for _zsh_highlight.  Without this, subsequent
      # zle-line-pre-redraw hooks won't run, since add-zle-hook-widget happens to
      # call us with $? == 1 in the common case.
      #
      true && _zsh_highlight "$@"
    }

    if [[ -o zle ]]; then
      add-zle-hook-widget zle-line-pre-redraw _history-substring-search-zle-line-pre-redraw
      add-zle-hook-widget zle-line-finish _history-substring-search-zle-line-finish
    fi
  else
    #
    # The following snippet was taken from the zsh-syntax-highlighting project:
    # https://github.com/zsh-users/zsh-syntax-highlighting/blob/56b134f5d62ae3d4e66c7f52bd0cc2595f9b305b/zsh-syntax-highlighting.zsh#L126-161
    #
    # SPDX-SnippetBegin
    # SPDX-License-Identifier: BSD-3-Clause
    # SPDX-SnippetCopyrightText: 2010-2011 zsh-syntax-highlighting contributors
    #--------------8<-------------------8<-------------------8<-----------------
    # Rebind all ZLE widgets to make them invoke _zsh_highlights.
    _zsh_highlight_bind_widgets()
    {
      # Load ZSH module zsh/zleparameter, needed to override user defined widgets.
      zmodload zsh/zleparameter 2>/dev/null || {
        echo 'zsh-syntax-highlighting: failed loading zsh/zleparameter.' >&2
        return 1
      }

      # Override ZLE widgets to make them invoke _zsh_highlight.
      local cur_widget
      for cur_widget in ${${(f)"$(builtin zle -la)"}:#(.*|_*|orig-*|run-help|which-command|beep|yank*)}; do
        case $widgets[$cur_widget] in

          # Already rebound event: do nothing.
          user:$cur_widget|user:_zsh_highlight_widget_*);;

          # User defined widget: override and rebind old one with prefix "orig-".
          user:*) eval "zle -N orig-$cur_widget ${widgets[$cur_widget]#*:}; \
                        _zsh_highlight_widget_$cur_widget() { builtin zle orig-$cur_widget -- \"\$@\" && _zsh_highlight }; \
                        zle -N $cur_widget _zsh_highlight_widget_$cur_widget";;

          # Completion widget: override and rebind old one with prefix "orig-".
          completion:*) eval "zle -C orig-$cur_widget ${${widgets[$cur_widget]#*:}/:/ }; \
                              _zsh_highlight_widget_$cur_widget() { builtin zle orig-$cur_widget -- \"\$@\" && _zsh_highlight }; \
                              zle -N $cur_widget _zsh_highlight_widget_$cur_widget";;

          # Builtin widget: override and make it call the builtin ".widget".
          builtin) eval "_zsh_highlight_widget_$cur_widget() { builtin zle .$cur_widget -- \"\$@\" && _zsh_highlight }; \
                         zle -N $cur_widget _zsh_highlight_widget_$cur_widget";;

          # Default: unhandled case.
          *) echo "zsh-syntax-highlighting: unhandled ZLE widget '$cur_widget'" >&2 ;;
        esac
      done
    }
    #-------------->8------------------->8------------------->8-----------------
    # SPDX-SnippetEnd

    _zsh_highlight_bind_widgets
  fi

  unfunction _history-substring-search-function-callable
fi

_history-substring-search-begin() { setopt localoptions extendedglob; wsh-history-begin }

_history-substring-search-end() {
  setopt localoptions extendedglob

  local highlight_memo=
  _history_substring_search_result=$BUFFER

  if [[ $_history_substring_search_zsh_5_9 -eq 1 ]]; then
    highlight_memo='memo=history-substring-search'
  fi

  # the search was successful so display the result properly by clearing away
  # existing highlights and moving the cursor to the end of the result buffer
  if [[ $_history_substring_search_refresh_display -eq 1 ]]; then
    if [[ -n $highlight_memo ]]; then
      region_highlight=( "${(@)region_highlight:#*${highlight_memo}*}" )
    else
      region_highlight=()
    fi
    CURSOR=${#BUFFER}
  fi

  # highlight command line using zsh-syntax-highlighting
  _zsh_highlight

  # highlight the search query inside the command line
  if [[ -n $_history_substring_search_query_highlight ]]; then
    # highlight first matching query parts
    local highlight_start_index=0
    local highlight_end_index=0
    local query_part
    for query_part in $_history_substring_search_query_parts; do
      local escaped_query_part=${query_part//(#m)[\][()|\\*?#<>~^]/\\$MATCH}
      # (i) get index of pattern
      local query_part_match_index="${${BUFFER:$highlight_start_index}[(i)(#$HISTORY_SUBSTRING_SEARCH_GLOBBING_FLAGS)${escaped_query_part}]}"
      if [[ $query_part_match_index -le ${#BUFFER:$highlight_start_index} ]]; then
        highlight_start_index=$(( $highlight_start_index + $query_part_match_index ))
        highlight_end_index=$(( $highlight_start_index + ${#query_part} ))
        region_highlight+=(
          "$(($highlight_start_index - 1)) $(($highlight_end_index - 1)) ${_history_substring_search_query_highlight}${highlight_memo:+,$highlight_memo}"
        )
      fi
    done
  fi

  # For debugging purposes:
  # zle -R "mn: "$_history_substring_search_match_index" m#: "${#_history_substring_search_matches}
  # read -k -t 200 && zle -U -- "$REPLY"

  #
  # When this function returns, z-sy-h runs its line-pre-redraw hook. It has no
  # logic for determining highlight priority, when two different memo= marked
  # region highlights overlap; instead, it always prioritises itself. Below is
  # a workaround for dealing with it.
  #
  if [[ $_history_substring_search_zsh_5_9 -eq 1 ]]; then
    zle -R
    #
    # After line redraw with desired highlight, wait for timeout or user input
    # before removing search highlight and exiting. This ensures no highlights
    # are left lingering after search is finished.
    #
    read -k -t ${HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_TIMEOUT:-1} && zle -U -- "$REPLY"
    region_highlight=( "${(@)region_highlight:#*${highlight_memo}*}" )
  fi

  # Exit successfully from the history-substring-search-* widgets.
  return 0
}

_history-substring-search-up-buffer() {
  #
  # Check if the UP arrow was pressed to move the cursor within a multi-line
  # buffer. This amounts to three tests:
  #
  # 1. $#buflines -gt 1.
  #
  # 2. $CURSOR -ne $#BUFFER.
  #
  # 3. Check if we are on the first line of the current multi-line buffer.
  #    If so, pressing UP would amount to leaving the multi-line buffer.
  #
  #    We check this by adding an extra "x" to $LBUFFER, which makes
  #    sure that xlbuflines is always equal to the number of lines
  #    until $CURSOR (including the line with the cursor on it).
  #
  local buflines XLBUFFER xlbuflines
  buflines=(${(f)BUFFER})
  XLBUFFER=$LBUFFER"x"
  xlbuflines=(${(f)XLBUFFER})

  if [[ $#buflines -gt 1 && $CURSOR -ne $#BUFFER && $#xlbuflines -ne 1 ]]; then
    zle up-line-or-history
    return 0
  fi

  return 1
}

_history-substring-search-down-buffer() {
  #
  # Check if the DOWN arrow was pressed to move the cursor within a multi-line
  # buffer. This amounts to three tests:
  #
  # 1. $#buflines -gt 1.
  #
  # 2. $CURSOR -ne $#BUFFER.
  #
  # 3. Check if we are on the last line of the current multi-line buffer.
  #    If so, pressing DOWN would amount to leaving the multi-line buffer.
  #
  #    We check this by adding an extra "x" to $RBUFFER, which makes
  #    sure that xrbuflines is always equal to the number of lines
  #    from $CURSOR (including the line with the cursor on it).
  #
  local buflines XRBUFFER xrbuflines
  buflines=(${(f)BUFFER})
  XRBUFFER="x"$RBUFFER
  xrbuflines=(${(f)XRBUFFER})

  if [[ $#buflines -gt 1 && $CURSOR -ne $#BUFFER && $#xrbuflines -ne 1 ]]; then
    zle down-line-or-history
    return 0
  fi

  return 1
}

_history-substring-search-up-history() {
  #
  # Behave like up in ZSH, except clear the $BUFFER
  # when beginning of history is reached like in Fish.
  #
  if [[ -z $_history_substring_search_query ]]; then

    # we have reached the absolute top of history
    if [[ $HISTNO -eq 1 ]]; then
      BUFFER=

    # going up from somewhere below the top of history
    else
      zle up-line-or-history
    fi

    return 0
  fi

  return 1
}

_history-substring-search-down-history() {
  #
  # Behave like down-history in ZSH, except clear the
  # $BUFFER when end of history is reached like in Fish.
  #
  if [[ -z $_history_substring_search_query ]]; then

    # going down from the absolute top of history
    if [[ $HISTNO -eq 1 && -z $BUFFER ]]; then
      BUFFER=${history[1]}
      _history_substring_search_refresh_display=1

    # going down from somewhere above the bottom of history
    else
      zle down-line-or-history
    fi

    return 0
  fi

  return 1
}

_history-substring-search-up-search() { wsh-history-navigate up }
_history-substring-search-down-search() { wsh-history-navigate down }
