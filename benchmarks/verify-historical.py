#!/usr/bin/env python3
"""Reconstruct the complete historical evidence suite from its pinned Git tree."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3'

with tempfile.TemporaryDirectory(prefix='wsh-historical-evidence-') as directory:
    source = subprocess.Popen(['git', 'archive', REVISION], cwd=ROOT, stdout=subprocess.PIPE)
    try:
        subprocess.run(['tar', '-xf', '-', '-C', directory], stdin=source.stdout, check=True)
    finally:
        source.stdout.close()
        result = source.wait()
    if result:
        raise SystemExit(result)
    gitdir = subprocess.check_output(['git', 'rev-parse', '--absolute-git-dir'], cwd=ROOT, text=True).strip()
    (Path(directory)/'.git').write_text('gitdir: '+gitdir+'\n')
    subprocess.run(['zsh', 'benchmarks/verify-retained-evidence.zsh'], cwd=directory, check=True)
print('PASS: historical evidence verified from '+REVISION)
