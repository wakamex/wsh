#!/usr/bin/env python3
"""Render the Homebrew formula for a Wsh source archive.

Usage: render-formula.py URL SHA256 REVISION OUTPUT

URL and SHA256 name the source archive; REVISION is the commit it was made from. The pinned
Zsh source comes from the native source lock in this checkout.
"""
import json
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[2]
url, sha256, revision, output = sys.argv[1:]
assert re.fullmatch(r'[0-9a-f]{64}', sha256) and re.fullmatch(r'[0-9a-f]{40}', revision), (sha256, revision)
lock = json.loads((root / 'build/zsh-sources/zsh-cad0d67c-native.json').read_text())
values = {'URL': url, 'SHA256': sha256, 'REVISION': revision, 'ZSH_URL': lock['archive_url'],
          'ZSH_SHA256': lock['archive_sha256'], 'ZSH_ARCHIVE': lock['archive_name']}
text = (root / 'packaging/homebrew/wsh.rb.in').read_text()
for key, value in values.items():
    text = text.replace('@' + key + '@', value)
assert not re.search(r'@[A-Z_]+@', text), 'unreplaced placeholder'
Path(output).write_text(text)
print(output)
