#!/usr/bin/env python3
"""Check catalog build validation against the actual retained reference files."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('catalog', root / 'build/plugin-catalog.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original = module.verify()
with tempfile.TemporaryDirectory() as tmp:
    module.CATALOG = Path(tmp) / 'catalog.json'
    mutations = [
        lambda d: d.update(schema_version=2),
        lambda d: d['entries'].append(copy.deepcopy(d['entries'][0])),
        lambda d: d['entries'][0].update(component='unknown'),
        lambda d: d['entries'][0].update(handoff='unknown'),
        lambda d: d['entries'][0].update(revision='not-a-revision'),
        lambda d: d['entries'][0].update(files=[]),
        lambda d: d['entries'][0]['files'][0].update(sha256='0' * 64),
        lambda d: d['entries'][0]['files'][0].update(source='/etc/passwd'),
    ]
    for mutate in mutations:
        data = copy.deepcopy(original)
        mutate(data)
        module.CATALOG.write_text(json.dumps(data))
        try:
            module.verify()
        except ValueError:
            pass
        else:
            raise AssertionError('invalid catalog accepted')
print('PASS: catalog schema, duplicates, components, handoffs, revisions, arity, fingerprints and source boundaries')
