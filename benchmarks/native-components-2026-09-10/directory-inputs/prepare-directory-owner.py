#!/usr/bin/env python3
"""Private complete data/query owner; retain pinned Zsh editor adapters."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
original = (root / 'third_party/zsh-z/z.plugin.zsh').read_text()
control = original.replace('local now=$EPOCHSECONDS', 'local now=${WSH_QUERY_NOW:-$EPOCHSECONDS}')
start = control.index('zshz() {')
end = control.index('\nalias ${ZSHZ_CMD', start)
wrapper = '''zshz() {
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
        print -r -- ${PWD/#${HOME}/\\~}
      else
        print -r -- $PWD
      fi
    fi
  fi
  return 0
}
'''
(out / 'control.zsh').write_text(control)
(out / 'candidate.zsh').write_text(control[:start] + wrapper + control[end:])
