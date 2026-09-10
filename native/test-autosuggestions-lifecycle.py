#!/usr/bin/env python3
"""Cancel an actual pending strategy child when the editor accepts Ctrl-C."""
import json
import os
from pathlib import Path
import sys
import time
root=Path(__file__).resolve().parents[1]
source=(root/'native/test-autosuggestions-owner.py').read_text().split("if MODE=='correctness':",1)[0]
namespace={'__file__':str(root/'native/test-autosuggestions-owner.py')}
exec(compile(source,str(root/'native/test-autosuggestions-owner.py'),'exec'),namespace)
namespace['CONFIG']+=r'''
_zsh_autosuggest_strategy_probe() { print -r -- "$1" >> $HOME/requests; sleep 30; suggestion="$1 result"; }
_pending() { print -nr -- $'\x1ePID:'"${_ZSH_AUTOSUGGEST_CHILD_PID-}|${_ZSH_AUTOSUGGEST_ASYNC_FD-}"$'\x1f'; }
zle -N _pending
bindkey '^Y' _pending
'''
if '--no-monitor' in sys.argv:namespace['CONFIG']+='\nunsetopt monitor\n'
shell=namespace['Shell']('candidate','pending-cancel','custom')
try:
 os.write(shell.fd,b'pending request')
 request=shell.home/'requests';end=time.monotonic()+5
 while not request.exists() or 'pending request' not in request.read_text():
  assert time.monotonic()<end;time.sleep(.005)
 offset=len(shell.output);os.write(shell.fd,b'\x19');shell.wait(b'\x1ePID:',offset)
 start=shell.output.index(b'\x1ePID:',offset)+5;shell.wait(b'\x1f',start)
 pid=int(shell.output[start:shell.output.index(b'|',start)])
 (namespace['OUT']/'before-cancel.json').write_text(json.dumps(dict(pid=pid,pgid=os.getpgid(pid),stat=Path('/proc',str(pid),'stat').read_text()),indent=2)+'\n')
 offset=len(shell.output);os.write(shell.fd,b'\x03');shell.wait(namespace['base'].READY,offset)
 offset=len(shell.output);os.write(shell.fd,b'\x19');shell.wait(b'\x1ePID:|\x1f',offset)
 end=time.monotonic()+3
 while Path('/proc',str(pid)).exists():
  assert time.monotonic()<end,('strategy child survived',pid,Path('/proc',str(pid),'stat').read_text());time.sleep(.01)
 (namespace['OUT']/'lifecycle.json').write_text(json.dumps(dict(ctrl_c_prompt=True,fd_cleared=True,child_reaped=True,pid=pid),indent=2)+'\n')
 print('PASS: pending strategy cancellation, fd cleanup, child reaping and prompt return')
finally:shell.close()
