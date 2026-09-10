#!/usr/bin/env python3
"""Create and verify the native installation inventory used by build and RPM tools."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inventory(root):
    records = []
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('non-regular payload: '+str(path))
        name = path.relative_to(root).as_posix()
        if name == 'manifest.json':
            continue
        records.append(dict(path=name, kind='file', mode=stat.S_IMODE(info.st_mode), size=info.st_size, sha256=digest(path)))
    return records

def verify(root):
    if root.is_symlink() or not root.is_dir() or (root/'manifest.json').is_symlink():
        raise ValueError('installation and manifest must not be symlinks')
    manifest = json.loads((root/'manifest.json').read_text())
    if manifest.get('schema_version') != 2 or manifest.get('format') != 'wsh-native-installation':
        raise ValueError('unsupported native installation format')
    if manifest.get('status') not in ('development', 'release') or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', manifest.get('version', '')):
        raise ValueError('invalid version or status')
    source = manifest.get('source_revision', '')
    if not re.fullmatch(r'[0-9a-f]{40}(\+dirty)?', source) or (manifest['status'] == 'release' and source.endswith('+dirty')):
        raise ValueError('invalid source revision')
    files = manifest.get('files')
    if not isinstance(files, list) or not files:
        raise ValueError('empty inventory')
    names = set()
    for item in files:
        name = item['path']
        path = PurePosixPath(name)
        if not name or path.is_absolute() or '..' in path.parts or path.as_posix() != name or name in names or name == 'manifest.json':
            raise ValueError('invalid or duplicate inventory path: '+name)
        names.add(name)
        if item['kind'] != 'file' or item['mode'] not in (0o644, 0o755) or type(item['size']) is not int or item['size'] < 0 or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ValueError('invalid inventory record: '+name)
    if files != inventory(root):
        raise ValueError('payload inventory mismatch')
    for name in ('bin/wsh', 'bin/wsh-runtime'):
        if name not in names or (root/name).stat().st_mode & 0o777 != 0o755:
            raise ValueError('missing native executable: '+name)
    lock = json.loads((root/'share/wsh/native-source-lock.json').read_text())
    if lock['native']['version'] != manifest['version'] or digest(root/'share/wsh/native-source-lock.json') != manifest['source_lock_sha256']:
        raise ValueError('native source lock mismatch')
    return manifest

def create(root, lock_path):
    lock = json.loads(lock_path.read_text())
    source = os.environ.get('WSH_SOURCE_REVISION')
    if not source:
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT):
            source += '+dirty'
    libraries = set()
    for record in inventory(root):
        path = root/record['path']
        with path.open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                continue
        result = subprocess.run(['readelf', '-d', path], capture_output=True, text=True, check=True)
        libraries.update(re.findall(r'Shared library: \[(.*?)\]', result.stdout))
    manifest = dict(schema_version=2, format='wsh-native-installation', status=os.environ.get('WSH_BUNDLE_STATUS', 'development'),
                    version=lock['native']['version'], source_revision=source, source_lock_sha256=digest(lock_path),
                    target=subprocess.check_output([os.environ.get('CC', 'gcc'), '-dumpmachine'], text=True).strip(),
                    builder=dict(base_image=os.environ.get('WSH_BUILDER_BASE_IMAGE'), source_date_epoch=os.environ.get('SOURCE_DATE_EPOCH'),
                                 compiler=subprocess.check_output([os.environ.get('CC', 'gcc'), '--version'], text=True).splitlines()[0],
                                 environment={k:os.environ.get(k, '') for k in ('CC','CFLAGS','CPPFLAGS','LDFLAGS','LIBS','LANG','LC_ALL','TZ','WSH_BUILD_JOBS')}),
                    zsh=dict(version=lock['version'], source_revision=lock['source_revision'], source_sha256=lock['archive_sha256']),
                    requirements=dict(dynamic_libraries=sorted(libraries), minimum_glibc=os.environ.get('WSH_MINIMUM_GLIBC')),
                    files=inventory(root))
    (root/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    verify(root)
    return digest(root/'manifest.json')

if __name__ == '__main__':
    try:
        if len(sys.argv) == 4 and sys.argv[1] == 'create':
            print(create(Path(sys.argv[2]), Path(sys.argv[3])))
        elif len(sys.argv) == 3 and sys.argv[1] == 'verify':
            verify(Path(sys.argv[2]))
            print('PASS: native installation inventory')
        else:
            raise ValueError('usage: native_manifest.py create ROOT LOCK | verify ROOT')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        raise SystemExit('error: '+str(exc))
