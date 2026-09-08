#!/usr/bin/env python3
"""Native dispatcher boundary checks and a matched command-latency experiment."""
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks/native-tools-2026-09-08'
WORK = Path('/var/tmp/wsh-native-tools')
NATIVE = WORK / 'installation/bin/wsh'
CONTROL = Path('/var/tmp/wsh-native-entry-prototype/native/bin/wsh')


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix='wsh-native-tools-') as directory:
        home = Path(directory)
        env = {'PATH': '/usr/bin:/bin', 'HOME': directory, 'ZDOTDIR': directory,
               'TERM': 'xterm-256color', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC'}
        def run(binary, arguments, environment=env):
            return subprocess.run([os.fsencode(binary), *[os.fsencode(a) for a in arguments]],
                                  env=environment, cwd=home, input=b'', capture_output=True, timeout=15)
        def passed(name):
            results.append(name)
        (home / '.zshenv').write_text('print startup-leaked; exit 91\n')
        version = run(NATIVE, ['--wsh-version'])
        assert version.returncode == 0 and not version.stderr and b'startup-leaked' not in version.stdout
        assert b'identity: compiled build; installed resources not verified' in version.stdout
        passed('version does not load user startup')
        for name in ('--wsh-version', '--wsh-help'):
            for extras in (['extra'], [b'\xff'], ['--'], ['-c', 'exit 7']):
                value = run(NATIVE, [name, *extras])
                assert value.returncode == 2 and not value.stdout and b'usage:' in value.stderr
        passed('extra and non-UTF-8 tool arguments rejected with status 2')
        (home / 'state').mkdir()
        (home / 'state/active.json').write_text('{broken')
        state_env = {k:v for k,v in env.items() if k not in ('HOME', 'ZDOTDIR')}
        state_env['WSH_STATE_ROOT'] = str(home / 'state')
        state_env['XDG_DATA_HOME'] = str(home / 'unavailable')
        assert run(NATIVE, ['--wsh-version'], state_env).stdout == version.stdout
        moved = home / 'byte-\udcff shell'
        shutil.copy2(NATIVE, moved)
        assert run(moved, ['--wsh-version'], state_env).stdout == version.stdout
        (home / 'manifest.json').write_text('{"zsh":"incompatible","status":"release"}')
        assert run(moved, ['--wsh-version'], state_env).stdout == version.stdout
        passed('version survives absent resources, corrupt state, missing HOME, non-UTF-8 executable path, and mismatched metadata')
        (home / '.zshenv').write_text('')
        for name in ('doctor', 'profile', 'version', 'update', 'run', '--wsh-version'):
            (home / name).write_text('print -rn -- "$1"; exit 23\n')
        cases = [['-f', '-c', 'print -rn -- "$1"; exit 31', 'zero', b'\xff --wsh-version'],
                 ['-f', '-c', 'print -rn -- "$1"', 'zero', '--wsh-version'],
                 ['--version'], ['-f', '--', '--wsh-version', b'\xff'],
                 ['-f', '-s', '--', '--wsh-version']]
        cases += [['-f', name, b'a \xff'] for name in ('doctor', 'profile', 'version', 'update', 'run')]
        for arguments in cases:
            a, b = run(CONTROL, arguments), run(NATIVE, arguments)
            assert (a.returncode, a.stdout, a.stderr) == (b.returncode, b.stdout, b.stderr), (arguments, a, b)
        passed('native flags, ordinary script names, delimiters, status and argument bytes match baseline')
        harness = home / 'harness.c'
        harness.write_text('#include <stdio.h>\n#include <string.h>\n#include <assert.h>\n'
            '#define ZSH_VERSION "test"\n#include "tools.c"\n'
            'int main(void) {\n'
            '  unsigned int state = 71031; char bytes[128]; char *args[] = {"wsh", bytes, 0};\n'
            '  for (int i=0; i<10000; ++i) {\n'
            '    for (int j=0; j<127; ++j) { state = state*1664525u+1013904223u; bytes[j]=(char)(1+state%255); }\n'
            '    bytes[127]=0; assert(wsh_cli(2,args)==-1);\n'
            '  }\n'
            '  args[1]="--wsh-version"; assert(wsh_cli(2,args)==0);\n'
            '  args[1]="--wsh-help"; assert(wsh_cli(2,args)==0);\n'
            '  assert(wsh_cli(0,args)==-1); return 0;\n}\n')
        compile_command = ['clang', '-std=c99', '-Wall', '-Wextra', '-Werror', '-g',
                           '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                           '-I'+str(ROOT/'native'), '-I'+str(WORK/'source/Src'), str(harness), '-o', str(home/'harness')]
        compiled = subprocess.run(compile_command, capture_output=True, check=True)
        sanitized = subprocess.run([home/'harness'], capture_output=True, timeout=15, check=True,
                                   env=dict(os.environ, ASAN_OPTIONS='detect_leaks=1:abort_on_error=1', UBSAN_OPTIONS='halt_on_error=1'))
        assert not sanitized.stderr
        (OUT/'sanitizer.log').write_bytes(compiled.stdout+compiled.stderr+sanitized.stdout+sanitized.stderr)
        (OUT/'harness.c').write_text(harness.read_text())
        passed('strict compiler diagnostics and ASan/UBSan: 10000 arbitrary byte arguments')
        affinity = sorted(os.sched_getaffinity(0))
        os.sched_setaffinity(0, {affinity[0]})
        for _ in range(5):
            run(NATIVE, ['--wsh-version']); run(CONTROL, ['--version'])
        samples=[]
        for pair in range(50):
            row={'pair': pair}
            for key in (('control','native') if pair%2==0 else ('native','control')):
                start=time.perf_counter_ns()
                result=run(CONTROL if key=='control' else NATIVE, ['--version' if key=='control' else '--wsh-version'])
                elapsed=(time.perf_counter_ns()-start)/1e6
                assert result.returncode==0
                row[key+'_ms']=elapsed
            samples.append(row)
        os.sched_setaffinity(0, affinity)
        differences=sorted(row['native_ms']-row['control_ms'] for row in samples)
        summary={'pairs':50,'statistic':'nearest-rank paired p95 native minus control process-exit milliseconds',
                 'paired_p95_ms':differences[47], 'gate_ms':3, 'passed':differences[47]<=3,
                 'cpu':affinity[0], 'environment':env | {'HOME':'<temporary fixture>', 'ZDOTDIR':'<temporary fixture>'},
                 'correctness':results, 'sanitizer_command':compile_command}
        (OUT/'version-samples.json').write_text(json.dumps(samples,indent=2)+'\n')
        (OUT/'version-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        assert summary['passed'],summary
        print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
