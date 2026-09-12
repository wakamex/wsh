#!/usr/bin/env python3
"""Retain exact local SRPM qualification inputs and outputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
build, repeat, vm = map(Path, sys.argv[1:4])
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
files = {}
for name in ('source.log','builder.log','builder.json','rebuild.log'):
    files[name] = build/name
files['packages.txt'] = build/'rebuild/packages.txt'
files['diagnostic/initial-rebuild.log'] = Path('/var/tmp/wsh-source-rpm-rebuild.log')
files['diagnostic/installed-checks.log'] = Path('/var/tmp/wsh-source-rpm-check-diagnostic-2.log')
files['source.rpm'] = next((build/'source/SRPMS').glob('*.src.rpm'))
files['source/wsh.tar.gz'] = build/'source/SOURCES/wsh-0.3.1.tar.gz'
files['source/wsh-repeat.tar.gz'] = repeat/'SOURCES/wsh-0.3.1.tar.gz'
assert sha(files['source/wsh.tar.gz']) == sha(files['source/wsh-repeat.tar.gz'])
queries = {}
for path in sorted((build/'rebuild/RPMS').rglob('*.rpm')):
    files['rpm/'+path.name] = path
    queries[path.name] = {flag: subprocess.check_output(['rpm','-qp',flag,path],text=True).splitlines() for flag in ('--list','--requires')}
assert len(queries) == 3, queries.keys()
debugsource = next(v for k,v in queries.items() if k.startswith('wsh-debugsource-'))
for suffix in ('/Src/wsh-startup.c','/Src/zsh.h','/Src/exec.c'):
    assert any(p.endswith(suffix) for p in debugsource['--list']), suffix
(build/'rpm-queries.json').write_text(json.dumps(queries,indent=2)+'\n')
files['rpm-queries.json'] = build/'rpm-queries.json'
for path in vm.iterdir():
    if path.is_file() and path.suffix in ('.json','.sh','.log','.bin'):
        files['vm/'+path.name] = path
for name in ('packaging/test-login.py','packaging/test-chsh-guest.py','packaging/vm.py','build/native_manifest.py'):
    files['test-source/'+name] = HERE.parents[1]/name
files['test-source/qualify-vm.py'] = HERE/'qualify-vm.py'
identity = {'status':'unsigned local development artifact','command':'./packaging/test-source-rpm.zsh '+str(build),
            'repeat_command':'python3 packaging/build-source-rpm.py '+str(repeat),
            'vm_command':'WSH_VM_WORK='+str(vm)+' python3 benchmarks/source-rpm-2026-09-11/qualify-vm.py '+str(next((build/'rebuild/RPMS').rglob('wsh-0.*.x86_64.rpm'))),
            'files':{name:sha(path) for name,path in sorted(files.items())}}
archive = HERE/'results.tar.gz'
with tarfile.open(archive,'w:gz') as t:
    for name,path in sorted(files.items()): t.add(path,arcname=name,recursive=False)
identity['archive_sha256'] = sha(archive)
(HERE/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
print('PASS: source archive agreement, complete debug sources and retained qualification artifacts')
