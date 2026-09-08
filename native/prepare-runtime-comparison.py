#!/usr/bin/env python3
"""Make unsigned comparison installations differing only in runtime bytes/manifest."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
source, control, candidate, out = [Path(p).resolve() for p in sys.argv[1:]]
out.mkdir(parents=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() + '+dirty'
result = dict(source_installation=str(source), source_manifest_sha256=sha(source / 'manifest.json'), status='unsigned development comparison', variants={})
for name, runtime in [('rust', control), ('c', candidate)]:
    stage = out / name
    shutil.copytree(source, stage, symlinks=True)
    shutil.copyfile(runtime, stage / 'bin/wsh-runtime')
    manifest = json.loads((stage / 'manifest.json').read_text())
    manifest['status'] = 'development'
    manifest['release_id'] = 'development-runtime-comparison-' + name + '-' + revision
    manifest['rust']['source_revision'] = revision
    manifest['rust']['lockfile_sha256'] = sha(ROOT / 'Cargo.lock')
    for entry in manifest['files']:
        if entry['path'] == 'bin/wsh-runtime':
            entry['sha256'] = sha(runtime); entry['size'] = runtime.stat().st_size
    needed = subprocess.check_output(['readelf', '-d', runtime], text=True)
    libraries = set(manifest['requirements']['dynamic_libraries'])
    libraries.update(line.split('[')[1].split(']')[0] for line in needed.splitlines() if '(NEEDED)' in line)
    manifest['requirements']['dynamic_libraries'] = sorted(libraries)
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    identity = sha(stage / 'manifest.json')
    destination = out / identity; stage.rename(destination)
    subprocess.run([ROOT / 'target/release/wsh', 'bundle', 'verify', destination], check=True, stdout=subprocess.DEVNULL)
    result['variants'][name] = dict(path=str(destination), manifest_sha256=identity, runtime_sha256=sha(runtime))
(out / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
