#!/usr/bin/env python3
"""Discard an oversized strategy response without displaying or retaining it."""
import json
import os
from pathlib import Path
import time
root=Path(__file__).resolve().parents[1]
source=(root/'native/test-autosuggestions-owner.py').read_text().split("if MODE=='correctness':",1)[0]
namespace={'__file__':str(root/'native/test-autosuggestions-owner.py')}
exec(compile(source,str(root/'native/test-autosuggestions-owner.py'),'exec'),namespace)
namespace['CONFIG']+=r'''
_zsh_autosuggest_strategy_probe() { print -r -- requested > $HOME/requested; suggestion="$1${(pl:1048576::x:)}"; }
_pending() { print -nr -- $'\x1ePENDING:'"${_ZSH_AUTOSUGGEST_CHILD_PID-}|${_ZSH_AUTOSUGGEST_ASYNC_FD-}"$'\x1f'; }
zle -N _pending
bindkey '^Y' _pending
'''
shell=namespace['Shell']('candidate','oversized','custom')
try:
 os.write(shell.fd,b'oversized')
 end=time.monotonic()+5
 while not (shell.home/'requested').exists():
  assert time.monotonic()<end;time.sleep(.005)
 cleared=False
 while time.monotonic()<end:
  offset=len(shell.output);os.write(shell.fd,b'\x19');shell.wait(b'\x1ePENDING:',offset)
  if b'\x1ePENDING:|\x1f' in shell.output[offset:]:cleared=True;break
  time.sleep(.01)
 assert cleared
 assert shell.state()[0]==''
 (namespace['OUT']/'bounds.json').write_text(json.dumps(dict(response_bytes=1048576+len('oversized'),limit_bytes=1048576,discarded=True,fd_cleared=True),indent=2)+'\n')
 print('PASS: oversized response is discarded and its pending descriptor is cleared')
finally:shell.close()
