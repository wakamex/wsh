#!/usr/bin/env python3
"""Verify retained upstream fingerprints and install the bounded recognition catalog."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'third_party/plugin-catalog/catalog.json'
ARITY = {'autosuggestions': 1, 'history': 1, 'syntax': 2, 'directory': 1, 'git-prompt': 2}
HANDOFFS = {
    'autosuggestions': ('pending-widget-binding', 'pending-widget-binding-legacy-zle-ignore'),
    'history': ('replace-history-hooks',),
    'syntax': ('main-parser-with-preserved-lifecycle',),
    'directory': ('preserve-directory-lifecycle',),
    'git-prompt': ('remove-prompt-collector-hooks',),
}


def verify():
    catalog = json.loads(CATALOG.read_text())
    if catalog['schema_version'] != 1:
        raise ValueError('unsupported catalog schema')
    seen = set()
    for entry in catalog['entries']:
        key = (entry['component'], entry['version'])
        if key in seen or entry['component'] not in ARITY:
            raise ValueError('invalid or duplicate component/version: ' + str(key))
        seen.add(key)
        if entry['handoff'] not in HANDOFFS[entry['component']]:
            raise ValueError('unsupported handoff family')
        if not re.fullmatch('[0-9a-f]{40}', entry['revision']):
            raise ValueError('invalid upstream revision')
        if not entry['repository'].startswith('https://github.com/'):
            raise ValueError('invalid upstream repository')
        if len(entry['files']) != ARITY[entry['component']]:
            raise ValueError('incorrect component file count')
        for record in entry['files']:
            source = ROOT / record['source']
            source.resolve().relative_to(ROOT / 'third_party')
            data = source.read_bytes()
            if not 0 < len(data) <= 131072:
                raise ValueError('reference exceeds the comparison bound')
            if hashlib.sha256(data).hexdigest() != record['sha256']:
                raise ValueError('reference fingerprint mismatch: ' + record['source'])
    return catalog


def install(destination):
    catalog = verify()
    destination.mkdir(parents=True, exist_ok=True)
    groups = {}
    for entry in catalog['entries']:
        refs = []
        for record in entry['files']:
            target = destination / record['sha256']
            shutil.copyfile(ROOT / record['source'], target)
            target.chmod(0o644)
            refs.append('plugin-catalog/' + target.name)
        row = '|'.join([entry['handoff'], *refs])
        group = groups.setdefault(entry['component'], [])
        if row not in group:
            group.append(row)
    lines = ['# Generated from verified upstream snapshots.', 'typeset -gA _WSH_PLUGIN_REFERENCES=(']
    for component, rows in groups.items():
        lines.append('  ' + shlex.quote(component) + ' ' + shlex.quote('\n'.join(rows)))
    lines.append(')')
    (destination / 'catalog.zsh').write_text('\n'.join(lines) + '\n')
    shutil.copyfile(CATALOG, destination / 'catalog.json')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--check':
        print('PASS:', len(verify()['entries']), 'upstream catalog snapshots and fingerprints')
    elif len(sys.argv) == 2:
        install(Path(sys.argv[1]))
    else:
        raise SystemExit('usage: plugin-catalog.py --check | DESTINATION')
