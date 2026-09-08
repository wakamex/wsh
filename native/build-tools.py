#!/usr/bin/env python3
"""Build the native tool slice on the retained, runnable startup prototype."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('/var/tmp/wsh-native-entry-prototype')
WORK = Path('/var/tmp/wsh-native-tools')
SOURCE = WORK / 'source'
EVIDENCE = WORK / 'foreground-evidence'


def run(arguments, **kwargs):
    print('+', repr([str(a) for a in arguments]), flush=True)
    return subprocess.run([str(a) for a in arguments], check=True, **kwargs)


def main():
    WORK.mkdir(exist_ok=True)
    EVIDENCE.mkdir(exist_ok=True)
    if not SOURCE.exists():
        shutil.copytree(BASE / 'source', SOURCE)
    destination = WORK / 'installation'
    if not destination.exists():
        shutil.copytree(BASE / 'native', destination)
    # Always derive the patch from the preserved baseline, never accumulate edits.
    original = (BASE / 'source/Src/init.c').read_text()
    source = original.replace('/**/\nmod_export int\nzsh_main(UNUSED(int argc), char **argv)',
        '#include "wsh-tools.c"\n\n/**/\nmod_export int\nzsh_main(int argc, char **argv)', 1)
    source = source.replace('    int t0;\n#ifdef USE_LOCALE',
        '    int t0;\n    int wsh_result = wsh_cli(argc, argv);\n'
        '    if (wsh_result >= 0)\n        return wsh_result;\n#ifdef USE_LOCALE', 1)
    assert source != original and source.count('wsh_cli(argc, argv)') == 1
    source = source.replace('    init_jobs(argv, environ);',
        '    if (wsh_doctor_fd >= 0)\n        argv = wsh_doctor_arguments;\n\n    init_jobs(argv, environ);', 1)
    source = source.replace('    fdtable[0] = fdtable[1] = fdtable[2] = FDT_EXTERNAL;',
        '    fdtable[0] = fdtable[1] = fdtable[2] = FDT_EXTERNAL;\n'
        '    if (wsh_doctor_fd >= 0)\n        fdtable[wsh_doctor_fd] = FDT_INTERNAL;', 1)
    source = source.replace('    run_init_scripts();', '    run_init_scripts();\n    wsh_doctor_finish();', 1)
    source = source.replace('    init_jobs(argv, environ);',
        '    if (wsh_foreground_count)\n        argv = wsh_foreground_arguments;\n\n    init_jobs(argv, environ);', 1)
    source = source.replace('    init_misc(cmd, zsh_name);',
        '    init_misc(cmd, zsh_name);\n    wsh_foreground_run();', 1)
    (SOURCE / 'Src/init.c').write_text(source)
    shutil.copy2(ROOT / 'native/foreground.c', SOURCE / 'Src/wsh-foreground.c')
    shutil.copy2(ROOT / 'native/doctor.c', SOURCE / 'Src/wsh-doctor.c')
    shutil.copy2(ROOT / 'native/tools.c', SOURCE / 'Src/wsh-tools.c')
    inputs = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((ROOT / 'native').rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    inputs['baseline-init.c'] = hashlib.sha256(original.encode()).hexdigest()
    identity = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    lock = json.loads((ROOT / 'build/zsh-sources/zsh-cad0d67c.json').read_text())
    definitions = {
        'WSH_VERSION': '0.3.1-native-tools', 'WSH_SOURCE_REVISION': revision,
        'WSH_INPUTS_SHA256': identity, 'WSH_ZSH_SOURCE_REVISION': lock['source_revision'],
        'WSH_TARGET': 'x86_64-linux-gnu',
    }
    header = ''.join(f'#define {key} {json.dumps(value)}\n' for key, value in definitions.items())
    (SOURCE / 'Src/wsh-build.h').write_text(header)
    environment = dict(os.environ, LC_ALL='C.UTF-8', LANG='C.UTF-8', TZ='UTC')
    run(['make', '-j8'], cwd=SOURCE, env=environment)
    for name in ('wsh', 'zsh'):
        shutil.copy2(SOURCE / 'Src/zsh', destination / 'bin' / name)
    manifest = json.loads((destination / 'manifest.json').read_text())
    manifest['release_id'] = 'development-native-tools'
    manifest['files'] = [{'path': str(p.relative_to(destination)), 'kind': 'file',
        'mode': p.stat().st_mode & 0o777, 'size': p.stat().st_size,
        'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted(destination.rglob('*')) if p.is_file() and p.name != 'manifest.json']
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    record = {'source_revision': revision, 'inputs': inputs, 'build_identity': definitions,
              'binary_sha256': hashlib.sha256((destination / 'bin/wsh').read_bytes()).hexdigest(),
              'control_sha256': hashlib.sha256((BASE / 'native/bin/wsh').read_bytes()).hexdigest(),
              'compiler': subprocess.check_output(['gcc', '--version'], text=True),
              'configure': subprocess.check_output([str(SOURCE / 'config.status'), '--config'], cwd=SOURCE, text=True),
              'build_command': 'python3 native/build-tools.py', 'environment': {k: environment[k] for k in ('LC_ALL', 'LANG', 'TZ')}}
    (EVIDENCE / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
    (EVIDENCE / 'wsh-build.h').write_text(header)
    print(destination / 'bin/wsh')


if __name__ == '__main__':
    main()
