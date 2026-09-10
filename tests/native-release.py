#!/usr/bin/env python3
"""Require agreement on real product bytes before staging release assets."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
package,manifest=map(lambda p:Path(p).resolve(),sys.argv[1:])
with tempfile.TemporaryDirectory(prefix='wsh-release-stage-') as directory:
    work=Path(directory)
    for worker in ('a','b'):
        target=work/worker;target.mkdir()
        shutil.copy2(package,target/package.name)
        shutil.copy2(manifest,target/'wsh.manifest.json')
        outputs=[dict(name=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(target.iterdir())]
        (target/('build-record-'+worker+'.json')).write_text(json.dumps(dict(outputs=outputs)))
    def run(output):
        return subprocess.run([sys.executable,root/'build/native-release.py','compare','a','b',output],cwd=work,capture_output=True)
    assert run('valid').returncode==0
    assert (work/'valid'/package.name).read_bytes()==package.read_bytes()
    path=work/'b'/package.name;original=path.read_bytes();path.write_bytes(original+b'altered')
    assert run('altered').returncode!=0
    path.write_bytes(original)
    record=work/'b/build-record-b.json';data=json.loads(record.read_text());data['outputs'][0]['sha256']='0'*64;record.write_text(json.dumps(data))
    assert run('bad-record').returncode!=0
    (work/'b/extra.rpm').write_bytes(b'additional package')
    assert run('extra').returncode!=0
print('PASS: real RPM agreement, changed bytes, invalid record and extra product rejection')
