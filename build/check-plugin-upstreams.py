#!/usr/bin/env python3
"""Report changed upstream plugin bytes without executing or updating them."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plugin_catalog', ROOT/'build/plugin-catalog.py')
catalog_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog_module)


def fetch_json(endpoint):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'wsh-upstream-monitor', 'X-GitHub-Api-Version': '2022-11-28'}
    if os.environ.get('GH_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
    with urlopen(Request('https://api.github.com/' + endpoint, headers=headers), timeout=30) as response:
        data = response.read(1048577)
    if len(data) > 1048576:
        raise ValueError('API response exceeds limit')
    return json.loads(data)


def file_bytes(record):
    if record.get('type') != 'file' or record.get('encoding') != 'base64':
        raise ValueError('expected an inline base64 file')
    data = base64.b64decode(record['content'].replace('\n', ''), validate=True)
    if not 0 < len(data) <= 131072 or record['size'] != len(data):
        raise ValueError('invalid file size')
    oid = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if record['sha'] != oid:
        raise ValueError('Git blob identity mismatch')
    return data


def inspect(upstreams, entries, output, fetch=fetch_json):
    output.mkdir(parents=True, exist_ok=True)
    heads = {}
    results = []
    for row in upstreams:
        result = dict(component=row['component'], repository=row['repository'], branch=row['branch'])
        try:
            repo = row['repository'].removeprefix('https://github.com/')
            key = (repo, row['branch'])
            if key not in heads:
                revision = fetch('repos/' + repo + '/commits/' + quote(row['branch'], safe=''))['sha']
                if not re.fullmatch('[0-9a-f]{40}', revision):
                    raise ValueError('invalid upstream commit')
                heads[key] = revision
            revision = heads[key]
            result.update(revision=revision, files=[])
            for path in row['paths']:
                record = fetch('repos/' + repo + '/contents/' + quote(path, safe='/') + '?ref=' + revision)
                if record.get('path') != path:
                    raise ValueError('API returned a different path')
                data = file_bytes(record)
                digest = hashlib.sha256(data).hexdigest()
                (output/digest).write_bytes(data)
                result['files'].append(dict(path=path, sha256=digest))
            expected = [r['sha256'] for r in result['files']]
            matches = [e for e in entries if e['component'] == row['component'] and e['repository'] == row['repository'] and [f['upstream_path'] for f in e['files']] == row['paths']]
            result['status'] = 'known' if any([f['sha256'] for f in e['files']] == expected for e in matches) else 'changed'
        except Exception as error:
            result.update(status='error', error=str(error))
        results.append(result)
    return results


def main():
    output = Path(sys.argv[1])
    results = inspect(catalog_module.upstreams(), catalog_module.verify()['entries'], output)
    (output/'results.json').write_text(json.dumps(results, indent=2)+'\n')
    lines = ['| Component | Upstream | Result |', '| --- | --- | --- |']
    for row in results:
        url = row['repository'] + ('/commit/' + row['revision'] if 'revision' in row else '')
        lines.append('| ' + row['component'] + ' | ' + url + ' | ' + row['status'] + ' |')
    summary = '\n'.join(lines) + '\n'
    (output/'summary.md').write_text(summary)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as destination:
            destination.write(summary)
    print(summary, end='')
    return int(any(row['status'] != 'known' for row in results))


if __name__ == '__main__':
    raise SystemExit(main())
