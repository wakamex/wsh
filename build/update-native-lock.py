#!/usr/bin/env python3
"""Refresh the explicit native C input lock after a reviewed source change."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
base=json.loads((ROOT/'build/zsh-sources/zsh-cad0d67c.json').read_text())
base['id']='zsh-cad0d67c-native'
base['output_name']='zsh-cad0d67c-native'
patch=ROOT/'build/zsh-patches/cad0d67c-native-entrypoint.patch'
base['source_patches'].append({'path':str(patch.relative_to(ROOT)),'sha256':hashlib.sha256(patch.read_bytes()).hexdigest()})
patch=ROOT/'build/zsh-patches/cad0d67c-native-completion.patch'
base['source_patches'].append({'path':str(patch.relative_to(ROOT)),'sha256':hashlib.sha256(patch.read_bytes()).hexdigest()})
base['native']={'version':re.search(r'^version = "([^"]+)"$',(ROOT/'Cargo.toml').read_text(),re.M)[1],
                'linked_modules':True,
                'sources':[{'path':'native/'+name+'.c','sha256':hashlib.sha256((ROOT/'native'/(name+'.c')).read_bytes()).hexdigest()}
                           for name in ('startup','tools','doctor','foreground','profile','profile-report','completion')]}
payload=json.dumps(base,indent=2)+'\n'
path=ROOT/'build/zsh-sources/zsh-cad0d67c-native.json'
if '--check' in sys.argv:
    assert path.read_text()==payload, 'native source lock is stale; run python3 build/update-native-lock.py'
else:path.write_text(payload)
