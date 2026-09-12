#!/usr/bin/env python3
"""Build and test an unpacked Wsh source RPM without Git metadata or downloads."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT/'build/zsh-sources/zsh-cad0d67c-native.json'
OUT = ROOT/'.rpm-build'


def verify():
    metadata = json.loads((ROOT/'source-info.json').read_text())
    for name, digest in metadata['files'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
    lock = json.loads(LOCK.read_text())
    assert lock['mode'] == 'canonical-commit'
    assert lock['native']['version'] == metadata['version']
    archive = ROOT/'build/cache'/lock['archive_name']
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == lock['archive_sha256'], 'Zsh source digest mismatch'
    return metadata


def environment(metadata):
    return dict(os.environ, WSH_SOURCE_REVISION=metadata['source_revision'],
                SOURCE_DATE_EPOCH=str(metadata['source_date_epoch']), WSH_BUNDLE_STATUS=metadata['status'],
                WSH_OFFLINE='1', LANG='C', LC_ALL='C', TZ='UTC')


def main():
    action = sys.argv[1]
    metadata = verify()
    env = environment(metadata)
    if action == 'verify':
        print('PASS: source inventory and pinned upstream archive')
    elif action == 'build':
        OUT.mkdir()
        # Preserve effective compiler flags for the final post-RPM inventory.
        (OUT/'environment.json').write_text(json.dumps({k: env[k] for k in
            ('CC','CFLAGS','CPPFLAGS','LDFLAGS','LIBS','WSH_BUILD_JOBS') if k in env})+'\n')
        reference_env = dict(env, WSH_ZSH_SOURCE_LOCK=str(ROOT/'build/zsh-sources/zsh-cad0d67c.json'), WSH_ZSH_OUTPUT_ROOT=str(OUT/'reference'))
        subprocess.run([ROOT/'build/build-zsh.zsh'], env=reference_env, check=True)
        native_env = dict(env, WSH_ZSH_OUTPUT_ROOT=str(OUT/'zsh'), WSH_BUNDLE_OUTPUT_ROOT=str(OUT/'bundles'), WSH_KEEP_BUILD_SOURCE='1')
        try:
            with (OUT/'native-build.log').open('w') as log:
                subprocess.run([ROOT/'build/build-native-installation.zsh'], env=native_env, stdout=log, stderr=subprocess.STDOUT, check=True)
        finally:
            # RPM may remove its build tree; retain compiler and upstream test
            # output in the outer build log on both success and failure.
            sys.stdout.write((OUT/'native-build.log').read_text())
            sys.stdout.flush()
        bundle = (OUT/'native-build.log').read_text().splitlines()[-1]
        assert Path(bundle).parent == OUT/'bundles'
        (OUT/'installation-path').write_text(bundle+'\n')
    elif action == 'install':
        bundle = Path((OUT/'installation-path').read_text().strip())
        destination = Path(sys.argv[2])
        shutil.copytree(bundle, destination)
        for path in (destination, *destination.rglob('*')):
            if path.is_dir(): path.chmod(0o755)
    elif action in ('finalize', 'check'):
        bundle = Path(sys.argv[2]).resolve()
        env.update(json.loads((OUT/'environment.json').read_text()))
        env['LIBS'] = env.get('LIBS', '') + ' -ljansson'
        if action == 'finalize':
            subprocess.run(['python3', ROOT/'build/native_manifest.py', 'create', bundle, LOCK], env=env, check=True)
            return
        subprocess.run([ROOT/'build/check-native-installation.zsh', bundle,
                        OUT/'reference/zsh-cad0d67c-wsh2', OUT/'checks'], env=env, check=True)
        print('PASS: source RPM final installed payload and complete native checks')
    else:
        raise SystemExit('expected verify, build, install, finalize or check')


if __name__ == '__main__':
    main()
