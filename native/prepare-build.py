#!/usr/bin/env python3
"""Verify locked native sources, prepare Zsh includes, and identify the build."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
lock_path=Path(sys.argv[1]).resolve()
lock=json.loads(lock_path.read_text())
native=lock['native']
assert re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',native['version']), 'invalid native version'
assert native['sources'] and len({entry['path'] for entry in native['sources']})==len(native['sources'])
for entry in native['sources']:
    assert re.fullmatch(r'native/[a-z-]+\.c',entry['path']), 'invalid native source path'
    assert hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest()==entry['sha256'], 'native source digest mismatch: '+entry['path']
revision=os.environ.get('WSH_SOURCE_REVISION')
if not revision:
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT):revision+='+dirty'
assert re.fullmatch(r'[a-f0-9]{40}(\+dirty)?',revision), 'invalid Wsh source revision'
build_status=os.environ.get('WSH_BUNDLE_STATUS','development')
assert build_status in ('development','release'), 'invalid WSH_BUNDLE_STATUS'
build_label='release build' if build_status=='release' else 'unsigned development artifact'
compiler=os.environ.get('CC','gcc')
definitions={'WSH_VERSION':native['version'],'WSH_SOURCE_REVISION':revision,
             'WSH_BUILD_LABEL':build_label,
             'WSH_INPUTS_SHA256':hashlib.sha256(lock_path.read_bytes()).hexdigest(),
             'WSH_ZSH_SOURCE_REVISION':lock['source_revision'],
             'WSH_TARGET':subprocess.check_output([compiler,'-dumpmachine'],text=True).strip()}
header=''.join('#define '+key+' '+json.dumps(value)+'\n' for key,value in definitions.items())
if len(sys.argv)>2:
    destination=Path(sys.argv[2])/'Src'
    for entry in native['sources']:
        source=ROOT/entry['path']
        shutil.copy2(source,destination/('wsh-'+source.name))
    (destination/'wsh-build.h').write_text(header)
identity = {'header': header,
            'compiler': subprocess.check_output([compiler, '--version'], text=True),
            'flags': {name: os.environ.get(name, '') for name in ('CC', 'CFLAGS', 'CPPFLAGS', 'LDFLAGS', 'LIBS', 'WSH_BUILDER_PACKAGE_LOCK_SHA256')},
            'builder_sha256': hashlib.sha256((ROOT/'build/build-zsh.zsh').read_bytes()).hexdigest(),
            'preparation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
print(hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest())
