#!/usr/bin/env python3
"""Reject altered payloads before native artifact assembly or RPM packaging."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'build'))
from native_manifest import create, verify
baseline=Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='wsh-native-inventory-') as directory:
    bundle=Path(directory)/'payload'
    shutil.copytree(baseline,bundle)
    for path in bundle.rglob('*'):
        if path.is_file():path.chmod(0o755 if path.parent == bundle/'bin' else 0o644)
    create(bundle,root/'build/zsh-sources/zsh-cad0d67c-native.json')
    verify(bundle)
    manifest=(bundle/'manifest.json').read_bytes()
    probe=bundle/'bin/wsh-runtime'
    original=probe.read_bytes()
    failures=0
    def rejected():
        global failures
        try:verify(bundle)
        except (ValueError,OSError,KeyError,TypeError):failures+=1
        else:raise AssertionError('invalid payload accepted')
    probe.write_bytes(original+b'altered');rejected();probe.write_bytes(original)
    probe.chmod(0o644);rejected();probe.chmod(0o755)
    probe.unlink();rejected();probe.symlink_to(baseline/'bin/wsh-runtime');rejected();probe.unlink();probe.write_bytes(original);probe.chmod(0o755)
    extra=bundle/'extra';extra.write_text('extra');rejected();extra.unlink()
    extra.symlink_to(baseline,target_is_directory=True);rejected();extra.unlink()
    for field,value in [('schema_version',1),('source_revision','unknown'),('version','unversioned')]:
        data=json.loads(manifest);data[field]=value;(bundle/'manifest.json').write_text(json.dumps(data));rejected()
    for name in ['../outside','/absolute','bin/../wsh','bin//wsh','manifest.json']:
        data=json.loads(manifest);data['files'][0]['path']=name;(bundle/'manifest.json').write_text(json.dumps(data));rejected()
    data=json.loads(manifest);data['files'].append(data['files'][0]);(bundle/'manifest.json').write_text(json.dumps(data));rejected()
    (bundle/'manifest.json').write_bytes(manifest);verify(bundle)
    print('PASS:',failures,'native manifest tampering, inventory, mode, symlink and metadata rejections')
