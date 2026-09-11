#!/usr/bin/env python3
"""Check monitor decisions; live GitHub response qualification is retained separately."""
import base64
import hashlib
import importlib.util
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('monitor', root/'build/check-plugin-upstreams.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
data = (root/'third_party/zsh-autosuggestions/known-0.7.0.zsh').read_bytes()
record = dict(type='file', encoding='base64', size=len(data), content=base64.b64encode(data).decode(), sha=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(), path='zsh-autosuggestions.zsh')
assert module.file_bytes(record) == data
for change in ({'type':'symlink'}, {'encoding':'none'}, {'size':1}, {'sha':'0'*40}, {'content':'not base64!'}):
    try:
        module.file_bytes(dict(record, **change))
    except ValueError:
        pass
    else:
        raise AssertionError(change)
rows = module.catalog_module.upstreams()[:1]
entries = module.catalog_module.verify()['entries']
with tempfile.TemporaryDirectory() as tmp:
    def fetch(endpoint):
        return {'sha':'a'*40} if '/commits/' in endpoint else record
    result = module.inspect(rows, entries, Path(tmp), fetch)
    assert result[0]['status'] == 'known'
    assert module.inspect(rows, [], Path(tmp), fetch)[0]['status'] == 'changed'
    def fail(endpoint):
        raise OSError('offline fixture')
    assert module.inspect(rows, entries, Path(tmp), fail)[0]['status'] == 'error'
    original = record['path']
    record['path'] = 'different-file'
    assert module.inspect(rows, entries, Path(tmp), fetch)[0]['status'] == 'error'
    record['path'] = original
print('PASS: monitor known/changed/error, response type, encoding, size, Git blob and path validation')
