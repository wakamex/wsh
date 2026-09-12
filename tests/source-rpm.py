#!/usr/bin/env python3
"""Inspect a real SRPM and reject altered or missing source in an unpacked build."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

srpm = Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix='wsh-srpm-') as directory:
    work = Path(directory)
    names = subprocess.check_output(['rpm','-qpl',srpm],text=True).splitlines()
    assert len(names) == 3 and all(Path(n).name == n for n in names), names
    source = subprocess.Popen(['rpm2cpio', srpm], stdout=subprocess.PIPE)
    subprocess.run(['cpio','-idm','--quiet'],stdin=source.stdout,cwd=work,check=True)
    source.stdout.close()
    assert source.wait() == 0
    spec = (work/'wsh.spec').read_text()
    assert '%build\n' in spec and 'source-build.py build' in spec
    assert '%check\n' in spec and 'source-build.py check' in spec
    assert '%global __os_install_post %{__os_install_post}' in spec and 'source-build.py finalize' in spec
    assert 'debug_package' not in spec
    requires = subprocess.check_output(['rpm','-qp','--requires',srpm],text=True)
    for dependency in ('gcc','python3 >= 3.9','jansson-devel','zsh'):
        assert dependency in requires
    archive = next(work.glob('wsh-*.tar.gz'))
    with tarfile.open(archive) as t:
        for member in t.getmembers():
            assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
            assert '.git' not in Path(member.name).parts and Path(member.name).suffix not in ('.o','.so','.zwc')
            assert not t.extractfile(member).read(4) == b'\x7fELF', member.name
        # The preceding checks restrict this self-produced archive to regular relative files.
        t.extractall(work/'source')
    root = next((work/'source').iterdir())
    metadata = json.loads((root/'source-info.json').read_text())
    lock = json.loads((root/'build/zsh-sources/zsh-cad0d67c-native.json').read_text())
    cache = root/'build/cache';cache.mkdir()
    upstream = cache/lock['archive_name']
    shutil.copyfile(work/lock['archive_name'],upstream)
    def verify():
        return subprocess.run(['python3', root/'packaging/source-build.py','verify'],capture_output=True)
    assert verify().returncode == 0
    upstream.rename(upstream.with_suffix('.missing'))
    assert verify().returncode != 0
    env = dict(os.environ, WSH_OFFLINE='1', WSH_SOURCE_REVISION=metadata['source_revision'], WSH_ZSH_OUTPUT_ROOT=str(work/'missing-build'))
    result = subprocess.run(['zsh',root/'build/build-zsh.zsh'],env=env,capture_output=True)
    assert result.returncode != 0 and b'offline Zsh source archive is missing' in result.stderr
    upstream.with_suffix('.missing').rename(upstream)
    with upstream.open('ab') as stream: stream.write(b'altered')
    assert verify().returncode != 0
    shutil.copyfile(work/lock['archive_name'],upstream)
    with (root/'native/startup.c').open('ab') as stream: stream.write(b'altered')
    assert verify().returncode != 0
print('PASS: real SRPM sources, dependencies, build/check phases, no prebuilt payload and offline source integrity')
