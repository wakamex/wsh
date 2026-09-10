#!/usr/bin/env python3
"""Extend the real editor comparison with complete-controller strategy and lifecycle modes."""
from pathlib import Path
import subprocess
import json
import sys
root=Path(__file__).resolve().parents[1]
binary,module,fixture,out=map(Path,sys.argv[1:5]);mode=sys.argv[5]
out.mkdir(parents=True,exist_ok=True)
s=(root/'native/test-autosuggestions-owner.py').read_text().replace('ROOT=Path(__file__).resolve().parents[1]','ROOT=Path('+repr(str(root))+')')
s=s.replace("('sync','async','vi','custom','completion')","('sync','async','vi','custom','completion','completion-sync','ignore','previous','manual','nomonitor')")
s=s.replace("mode=='completion'","mode.startswith('completion')").replace("mode!='completion'","not mode.startswith('completion')")
s=s.replace('[[ $WSH_TEST_MODE == completion ]]','[[ $WSH_TEST_MODE == completion* ]]')
s=s.replace('[[ $WSH_TEST_MODE == sync ]]','[[ $WSH_TEST_MODE == (sync|completion-sync) ]]')
s=s.replace("[[ $WSH_TEST_MODE == vi ]]",'''if [[ $WSH_TEST_MODE == ignore ]]; then
 print -s -- 'echo value ignored'
 ZSH_AUTOSUGGEST_HISTORY_IGNORE='*ignored'
fi
if [[ $WSH_TEST_MODE == previous ]]; then
 print -s -- 'previous context'
 print -s -- 'echo value newest'
 print -s -- 'different context'
 print -s -- 'echo value alternate'
 print -s -- 'previous context'
 ZSH_AUTOSUGGEST_STRATEGY=(match_prev_cmd)
fi
[[ $WSH_TEST_MODE == manual ]] && ZSH_AUTOSUGGEST_MANUAL_REBIND=1
[[ $WSH_TEST_MODE == nomonitor ]] && unsetopt monitor
[[ $WSH_TEST_MODE == vi ]]''')
s=s.replace("bindkey '^X' _custom", "zle -N 'odd widget; $(touch should-not-exist)' _custom\nbindkey '^X' 'odd widget; $(touch should-not-exist)'")
script=out/'run.py';script.write_text(s)
subprocess.run([sys.executable,script,binary,module,fixture,out,mode],check=True)

markers={owner:[str(p.relative_to(out)) for home in out.glob(owner+'-*') for p in home.rglob('should-not-exist')] for owner in ('control','candidate')}
(out/'widget-names.json').write_text(json.dumps(markers,indent=2)+'\n')
assert not markers['candidate'], "native controller executed a widget name"
