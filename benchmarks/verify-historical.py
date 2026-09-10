#!/usr/bin/env python3
"""Verify pre-migration evidence against its immutable source tree."""
import hashlib
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
REVISION='abece214b0c56e00204ce3b5995eb7f631ebcd6d'
# Historical reports and inputs remain immutable in the current checkout too.
entries=subprocess.check_output(['git','ls-tree','-rz',REVISION,'--','benchmarks'],cwd=ROOT).split(b'\0')
for entry in entries:
    if not entry:continue
    header,name=entry.split(b'\t',1)
    path=name.decode()
    if path=='benchmarks/verify-retained-evidence.zsh':continue
    mode,kind,digest=header.split()
    assert kind==b'blob'
    content=(ROOT/path).read_bytes()
    actual=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest().encode()
    assert actual==digest,'historical evidence changed: '+path
with tempfile.TemporaryDirectory(prefix='wsh-historical-evidence-') as directory:
    source=subprocess.Popen(['git','archive',REVISION],cwd=ROOT,stdout=subprocess.PIPE)
    extraction=subprocess.run(['tar','-xf','-','-C',directory],stdin=source.stdout)
    source.stdout.close()
    assert source.wait()==0 and extraction.returncode==0
    gitdir=subprocess.check_output(['git','rev-parse','--absolute-git-dir'],cwd=ROOT,text=True).strip()
    (Path(directory)/'.git').write_text('gitdir: '+gitdir+'\n')
    subprocess.run(['zsh','benchmarks/verify-retained-evidence.zsh'],cwd=directory,check=True)
print('PASS: immutable pre-migration evidence and historical source identities')
