#!/usr/bin/env python3
"""Build the native SDK from an immutable base and exact signed RPM inputs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

root=Path(__file__).resolve().parents[1]
inputs=[root/'build'/name for name in ('Containerfile.native-builder','native-sdk-packages.json','native-sdk-installed.lock')]
identity=hashlib.sha256(b''.join(p.read_bytes() for p in inputs)).hexdigest()
name='localhost/wsh-native-builder:'+identity[:24]
if subprocess.run(['podman','image','exists',name]).returncode:
    cache=root/'build/cache/native-sdk';cache.mkdir(parents=True,exist_ok=True)
    for record in json.loads(inputs[1].read_text()):
        path=cache/record['name']
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
            temporary=path.with_suffix('.download')
            urllib.request.urlretrieve(record['url'],temporary)
            assert hashlib.sha256(temporary.read_bytes()).hexdigest()==record['sha256'],record['name']
            temporary.replace(path)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==record['sha256']
    with tempfile.TemporaryDirectory(prefix='wsh-native-sdk-') as directory:
        context=Path(directory)
        for record in json.loads(inputs[1].read_text()):
            shutil.copy2(cache/record['name'],context/record['name'])
        shutil.copy2(inputs[2],context/'installed.lock')
        subprocess.run(['podman','build','--network=none','--label','org.wsh.inputs='+identity,'-t',name,'-f',str(inputs[0]),str(context)],check=True,stdout=sys.stderr)
info=json.loads(subprocess.check_output(['podman','image','inspect',name]))[0]
assert info['Config']['Labels']['org.wsh.inputs']==identity
print('sha256:'+info['Id'].removeprefix('sha256:'))
