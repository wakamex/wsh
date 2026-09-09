#!/usr/bin/env python3
"""Split the real native compinit without trace work inside its spans."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[1];BUNDLE=Path(sys.argv[1]).resolve();OUT=Path(sys.argv[2]).resolve();OUT.mkdir(parents=True)
source=next((BUNDLE/'share/zsh').glob('*/functions/compinit'));text=source.read_text()
markers=[('autoload -RUz compaudit\n','audit_start'),('# Make sure compdump is available, even if we aren\'t going to use it.','audit_end'),('  for _i_dir in $fpath; do','scan_start'),('  # If autodumping was requested, do it now.','scan_end'),('    compdump\n','dump')]
for old,label in markers:
    assert text.count(old)==1,(label,text.count(old))
    if label=='dump':text=text.replace(old,"    typeset -g _WSH_CI_dump_start=$EPOCHREALTIME\n"+old+"    typeset -g _WSH_CI_dump_end=$EPOCHREALTIME\n")
    else:text=text.replace(old,f'typeset -g _WSH_CI_{label}=$EPOCHREALTIME\n'+old)
(OUT/'compinit-timed').write_text(text)
script=OUT/'run.zsh';script.write_text('''zmodload zsh/datetime
unalias -m '*' 2>/dev/null
if [[ $1 == timed ]]; then
  functions[compinit]="$(< $2)"
else
  autoload -Uz +X compinit
fi
start=$EPOCHREALTIME
compinit -i -d "$HOME/dump" || exit 2
end=$EPOCHREALTIME
print -r -- "$start $end ${_WSH_CI_audit_start:-0} ${_WSH_CI_audit_end:-0} ${_WSH_CI_scan_start:-0} ${_WSH_CI_scan_end:-0} ${_WSH_CI_dump_start:-0} ${_WSH_CI_dump_end:-0}"
print -r -- "${(j:|:)fpath}" > "$HOME/fpath"
typeset -p _comps _services _patcomps _postpatcomps _compautos > "$HOME/mappings"
''')
rows=[]
for state in ['cold','warm']:
    for mode in ['plain','timed']:
        home=OUT/(state+'-'+mode);home.mkdir();
        if state=='warm':subprocess.run([BUNDLE/'bin/wsh','-df',script,'plain',OUT/'compinit-timed'],env=dict(PATH='/usr/bin:/bin',HOME=str(home),LC_ALL='C.UTF-8'),stdout=subprocess.DEVNULL,check=True)
    for pair in range(50):
        signatures={}
        for mode in (['plain','timed'] if pair%2==0 else ['timed','plain']):
            home=OUT/(state+'-'+mode)
            if state=='cold':(home/'dump').unlink(missing_ok=True)
            result=subprocess.run([BUNDLE/'bin/wsh','-df',script,mode,OUT/'compinit-timed'],env=dict(PATH='/usr/bin:/bin',HOME=str(home),LC_ALL='C.UTF-8'),capture_output=True,timeout=10,preexec_fn=lambda:os.sched_setaffinity(0,{0}))
            assert result.returncode==0 and not result.stderr,(result.stdout,result.stderr)
            clocks=result.stdout.decode().strip().split();assert len(clocks)==8,clocks
            values=list(map(Decimal,clocks));spans={key:float((values[b]-values[a])*1000) for key,a,b in [('total',0,1),('audit',2,3),('scan',4,5),('dump',6,7)]}
            # Hash canonical key/value tokens, independent of associative-array print order.
            mappings=(home/'mappings').read_text();signatures[mode]=sorted(mappings.split())
            rows.append(dict(state=state,mode=mode,pair=pair,clocks=clocks,spans_ms=spans))
        assert signatures['plain']==signatures['timed']
summary={}
for state in ['cold','warm']:
    a=[r for r in rows if r['state']==state];d=[]
    for pair in range(50):
        v={r['mode']:r['spans_ms']['total'] for r in a if r['pair']==pair};d.append(v['timed']-v['plain'])
    summary[state]=dict(instrumentation_paired_p95_ms=sorted(d)[47],spans_median_ms={key:sorted(r['spans_ms'][key] for r in a if r['mode']=='timed')[24] for key in ['total','audit','scan','dump']})
(OUT/'samples.json').write_text(json.dumps(rows,indent=2)+'\n');(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(OUT/'metadata.json').write_text(json.dumps(dict(command=sys.argv,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),timed_sha256=hashlib.sha256(text.encode()).hexdigest(),bundle_sha256=hashlib.sha256((BUNDLE/'manifest.json').read_bytes()).hexdigest(),cpu=0),indent=2)+'\n')
print(json.dumps(summary,indent=2))
