#!/usr/bin/env python3
"""Prepare a self-contained source RPM for an offline distro build."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def download_sources(revision, records, destination):
    """Preserve a public archive and check the build inputs against the checkout."""
    url = 'https://github.com/wakamex/wsh/archive/'+revision+'.tar.gz'
    urllib.request.urlretrieve(url, destination)
    with tarfile.open(destination) as archive:
        entries = {m.name.split('/', 1)[1]: archive.extractfile(m).read()
                   for m in archive.getmembers() if m.isfile()}
    for name, data, mode in records:
        assert entries[name] == data, 'published source differs: '+name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--release', default='1')
    parser.add_argument('--status', choices=('development', 'release'), default='development')
    args = parser.parse_args()
    assert re.fullmatch(r'[0-9]+(?:\.[0-9]+)*', args.release), 'invalid RPM release'
    version = (ROOT/'VERSION').read_text().strip()
    assert re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version), 'invalid version'
    revision = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=all'], cwd=ROOT))
    assert args.status != 'release' or not dirty, 'release source RPM requires a clean tree'
    if dirty: revision += '+dirty'
    epoch = int(subprocess.check_output(['git','show','-s','--format=%ct','HEAD'], cwd=ROOT))
    output = args.output.resolve()
    assert not output.exists(), 'use a new output directory'
    sources, specs = output/'SOURCES', output/'SPECS'
    sources.mkdir(parents=True); specs.mkdir()
    lock = json.loads((ROOT/'build/zsh-sources/zsh-cad0d67c-native.json').read_text())
    assert lock['mode'] == 'canonical-commit' and lock['native']['version'] == version
    cache = ROOT/'build/cache'/lock['archive_name']
    upstream = sources/lock['archive_name']
    if cache.exists(): shutil.copyfile(cache, upstream)
    else: urllib.request.urlretrieve(lock['archive_url'], upstream)
    assert hashlib.sha256(upstream.read_bytes()).hexdigest() == lock['archive_sha256'], 'Zsh source digest mismatch'
    paths = subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'], cwd=ROOT).decode().split('\0')
    roots = {'build','native','integration','third_party','themes','schemas','packaging','tests'}
    records = []
    for name in sorted(set(paths)):
        if not name: continue
        path = ROOT/name
        if not path.exists() or output in path.parents: continue
        if Path(name).parts[0] not in roots and not (len(Path(name).parts) == 1 and (path.suffix == '.md' or name in ('VERSION','LICENSE'))): continue
        assert path.is_file() and not path.is_symlink(), name
        data = path.read_bytes()
        assert not data.startswith(b'\x7fELF') and path.suffix not in ('.zwc','.o','.so'), 'prebuilt input: '+name
        records.append((name, data, 0o755 if path.stat().st_mode & 0o111 else 0o644))
    source_url = 'https://github.com/wakamex/wsh/archive/'+revision+'.tar.gz'
    source_archive = sources/f'wsh-{revision}.tar.gz'
    if args.status == 'release':
        # Keep the published upstream archive byte-for-byte. Do not inject build
        # metadata into it or pretend that a local repack has an upstream URL.
        download_sources(revision, records, source_archive)
    else:
        with source_archive.open('wb') as raw:
            with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=epoch) as compressed:
                with tarfile.open(fileobj=compressed, mode='w', format=tarfile.PAX_FORMAT) as archive:
                    for name, data, mode in records:
                        info = tarfile.TarInfo(f'wsh-{revision}/'+name)
                        info.size, info.mode, info.mtime = len(data), mode, epoch
                        archive.addfile(info, io.BytesIO(data))
    metadata = dict(version=version, source_revision=revision, source_date_epoch=epoch, status=args.status,
                    files={name:hashlib.sha256(data).hexdigest() for name,data,mode in records})
    (sources/'wsh-source-info.json').write_text(json.dumps(metadata, indent=2)+'\n')
    spec = (ROOT/'packaging/wsh.spec').read_text()
    spec = '%global wsh_commit '+revision+'\n'+spec
    source = source_url+'#/'+source_archive.name if args.status == 'release' else source_archive.name
    spec = re.sub(r'^Source0:.*$', 'Source0:        '+source, spec, flags=re.M)
    spec = spec.replace('%{!?wsh_version:%global wsh_version 0.4.0}', '%global wsh_version '+version)
    spec = spec.replace('%{!?wsh_release:%global wsh_release 1}', '%global wsh_release '+args.release)
    spec = re.sub(r'^Source1:.*$', 'Source1:        '+lock['archive_url']+'#/'+lock['archive_name'], spec, flags=re.M)
    (specs/'wsh.spec').write_text(spec)
    for path in [*sources.iterdir(), *specs.iterdir()]:
        path.chmod(0o644)
        os.utime(path, (epoch, epoch))
    subprocess.run(['rpmbuild','-bs','--nodeps','--define','_topdir '+str(output),
                    '--define','use_source_date_epoch_as_buildtime 1', '--define','_buildhost wsh-source',
                    specs/'wsh.spec'], env=dict(os.environ, SOURCE_DATE_EPOCH=str(epoch), LC_ALL='C', TZ='UTC'), check=True)
    for path in sorted((output/'SRPMS').glob('*.src.rpm')): print(path)


if __name__ == '__main__':
    main()
