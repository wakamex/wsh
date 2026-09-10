#!/usr/bin/env python3
"""Collect and compare the deterministic native package and its installation inventory."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def collect(tag,worker,output):
    assert re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+',tag) and worker in ('a','b')
    output=Path(output);output.mkdir()
    floor=ROOT/'build/portable/glibc-2.28'
    bundles=list((floor/'bundles').glob('*/manifest.json'))
    rpms=list((floor/'rpm/RPMS').rglob('*.rpm'))
    assert len(bundles)==len(rpms)==1
    manifest=json.loads(bundles[0].read_text())
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert manifest['status']=='release' and 'v'+manifest['version']==tag and manifest['source_revision']==revision
    shutil.copy2(bundles[0],output/('wsh-'+tag+'.manifest.json'))
    shutil.copy2(rpms[0],output/rpms[0].name)
    outputs=[dict(name=p.name,sha256=digest(p)) for p in sorted(output.iterdir())]
    record=dict(format_version=1,worker=worker,repository=os.environ.get('GITHUB_REPOSITORY','local'),source_revision=revision,release_id=tag,
                workflow=dict(sha=os.environ.get('GITHUB_WORKFLOW_SHA',revision),ref=os.environ.get('GITHUB_WORKFLOW_REF','local'),run_id=os.environ.get('GITHUB_RUN_ID','local'),run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT','local')),
                outputs=outputs)
    (output/('build-record-'+worker+'.json')).write_text(json.dumps(record,indent=2)+'\n')
def compare(left,right,output):
    left,right,output=map(Path,(left,right,output));output.mkdir()
    names=lambda p: sorted(x.name for x in p.iterdir() if x.name.endswith(('.rpm','.manifest.json')))
    files=names(left)
    assert len(files)==2 and files==names(right) and sum(n.endswith('.rpm') for n in files)==1
    for name in files:
        assert (left/name).read_bytes()==(right/name).read_bytes(),name
        shutil.copy2(left/name,output/name)
    for worker,path in [('a',left),('b',right)]:
        record=path/('build-record-'+worker+'.json')
        data=json.loads(record.read_text())
        assert sorted(x['name'] for x in data['outputs'])==files
        assert all(x['sha256']==digest(path/x['name']) for x in data['outputs'])
        shutil.copy2(record,output/record.name)
    (output/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.name+'\n' for p in sorted(output.iterdir())))
    Path('product-assets.txt').write_text('\n'.join(files)+'\n')
    Path('attested-assets.txt').write_text('\n'.join(sorted(p.name for p in output.iterdir()))+'\n')
if __name__=='__main__':
    if sys.argv[1]=='collect':collect(*sys.argv[2:])
    elif sys.argv[1]=='compare':compare(*sys.argv[2:])
    else:raise SystemExit('expected collect or compare')
