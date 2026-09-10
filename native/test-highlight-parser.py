#!/usr/bin/env python3
"""Run every original fixture independently so one parser error cannot hide later cases."""
import json
import os
from pathlib import Path
import subprocess
import sys
binary,fixture,out=[Path(p).resolve() for p in sys.argv[1:]]
out.mkdir(parents=True,exist_ok=True)
home=out/'home';home.mkdir(exist_ok=True)
rows=[]
for owner in ('control','candidate'):
    root=fixture/owner;driver=root/'tests/test-highlighting.zsh'
    source=driver.read_text().replace('for data_file in $root/highlighters/$1/test-data/*.zsh; do','for data_file in $WSH_TEST_CASE; do')
    selected=root/'tests/test-selected.zsh';selected.write_text(source)
    for case in sorted((root/'highlighters').glob('*/test-data/*.zsh')):
        name=case.parent.parent.name+'/'+case.name
        target=out/owner/name;target.parent.mkdir(parents=True,exist_ok=True)
        env=dict(PATH='/usr/bin:/bin',HOME=str(home),ZDOTDIR=str(home),WSH_TEST_CASE='./'+str(case.relative_to(root)),LC_ALL='C.UTF-8',TERM='xterm-256color')
        env.update({k:v for k,v in os.environ.items() if k.endswith('SAN_OPTIONS')})
        try:
            run=subprocess.run([binary,'-df','./tests/test-selected.zsh',case.parent.parent.name],cwd=root,env=env,capture_output=True,timeout=10)
            text=(run.stdout+run.stderr).decode(errors='replace')
            failed=[line for line in text.splitlines() if line.startswith('not ok') and '# TODO' not in line and '# SKIP' not in line]
            passed=run.returncode==0 and not failed and 'Bail out!' not in text and 'AddressSanitizer' not in text and 'runtime error:' not in text
            row=dict(owner=owner,case=name,status=run.returncode,failed_assertions=len(failed),passed=passed)
        except subprocess.TimeoutExpired as exc:
            text=((exc.stdout or b'')+(exc.stderr or b'')).decode(errors='replace');row=dict(owner=owner,case=name,status='timeout',passed=False)
        target.with_suffix('.log').write_text(text);rows.append(row)
        (out/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
summary={owner:dict(cases=sum(r['owner']==owner for r in rows),passed=sum(r['owner']==owner and r['passed'] for r in rows)) for owner in ('control','candidate')}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
