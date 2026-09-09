#!/usr/bin/env python3
"""Private native editor-action candidate with the real async/strategy adapters."""
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True)
s=(root/'third_party/zsh-autosuggestions/zsh-autosuggestions.zsh').read_text()
(out/'control.zsh').write_text(s)
def span(source,name):
    start=source.index(name+'() {');end=source.index('\n}',start)+2
    return start,end
start,end=span(s,'_zsh_autosuggest_fetch')
reference=s[start:end].replace('_zsh_autosuggest_fetch()', '_wsh_autosuggest_reference_fetch()',1)
for action in ('clear','modify','fetch','suggest','accept','execute','partial_accept','enable','disable','toggle'):
    name='_zsh_autosuggest_'+action;start,end=span(s,name)
    s=s[:start]+name+'() { wsh-autosuggest-action '+action+' "$@"; }'+s[end:]
start,end=span(s,'_zsh_autosuggest_strategy_history')
s=s[:start]+'''_zsh_autosuggest_strategy_history() { emulate -L zsh; setopt extendedglob; wsh-history-suggest "$1"; }'''+s[end:]
(out/'candidate.zsh').write_text(reference+'\n'+s)
