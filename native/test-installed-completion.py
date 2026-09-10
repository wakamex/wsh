#!/usr/bin/env python3
"""Qualify installed compinit against the unmodified pinned function and real ZLE."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUNDLE, REFERENCE, OUT = [Path(p).resolve() for p in sys.argv[1:4]]
MODE = sys.argv[4]
OUT.mkdir(parents=True, exist_ok=True)
fixture = OUT / 'reference'
fixture.mkdir(exist_ok=True)
functions = next((REFERENCE / 'share/zsh').glob('*/functions'))
(fixture / 'compinit').write_bytes((functions / 'compinit').read_bytes())
if not (fixture / 'seed').exists():
    subprocess.run([(REFERENCE / 'bin/wsh' if (REFERENCE / 'bin/wsh').exists() else REFERENCE / 'bin/zsh'), '-dfc', 'fpath=($1); autoload -Uz compinit; compinit -i -d "$2"', 'seed', functions, fixture / 'seed'], env=dict(PATH='/usr/bin:/bin', HOME=str(OUT), LC_ALL='C.UTF-8'), check=True)
results = []
if MODE == 'correctness':
    smoke = subprocess.run([BUNDLE / 'bin/wsh', '-dfc', 'zmodload zsh/parameter; (( $+builtins[wsh-completion-scan] ))'], capture_output=True)
    assert smoke.returncode == 0 and not smoke.stderr, smoke
    trap_functions = OUT / 'trap-functions'
    trap_functions.mkdir(exist_ok=True)
    (trap_functions / '_probe').write_text('#autoload -U\n')
    trap_script = OUT / 'debug-trap.zsh'
    trap_script.write_text('''fpath=("$1" "$2")
TRAPDEBUG() {
  if [[ ${funcstack[2]} == _wsh_completion_autoload ]]; then
    _i_line=()
    trap_ran=yes
  fi
}
autoload -Uz compinit
compinit -i -D || exit 1
[[ $trap_ran == yes && $_compautos[_probe] == -U ]] || exit 2
''')
    run = subprocess.run([BUNDLE / 'bin/wsh', '-df', trap_script, trap_functions, next((BUNDLE / 'share/zsh').glob('*/functions'))], capture_output=True)
    (OUT / 'debug-trap.stderr').write_bytes(run.stderr)
    assert run.returncode == 0 and not run.stderr, run
    results.append(dict(test='debug-trap-header-lifetime', status=0))
    for name in ('test-completion-header-dump', 'test-completion-scan'):
        source = (ROOT / 'native' / (name + '.py')).read_text().replace('$2 == candidate', '$2 == control')
        harness = OUT / (name + '.py')
        harness.write_text(source)
        run = subprocess.run([sys.executable, harness, BUNDLE, fixture, OUT / name], capture_output=True)
        (OUT / (name + '.stdout')).write_bytes(run.stdout)
        (OUT / (name + '.stderr')).write_bytes(run.stderr)
        results.append(dict(test=name, status=run.returncode))
        assert run.returncode == 0, run.stderr
    # The bundled function remains usable by regular Zsh through its upstream branch.
    fallback = OUT / 'fallback.zsh'
    fallback.write_text('''fpath=($1)
functions[compinit]="$(< $2)"
compinit -i -D || exit 1
[[ $_comps[git] == _git ]] || exit 2
''')
    raw = os.environ.get('WSH_REFERENCE_ZSH', '/var/tmp/wsh-native-entry-prototype/launcher/bin/zsh')
    run = subprocess.run([raw, '-df', fallback, functions, next((BUNDLE / 'share/zsh').glob('*/functions/compinit'))], env=dict(PATH='/usr/bin:/bin', HOME=str(OUT), LC_ALL='C.UTF-8'), capture_output=True)
    assert run.returncode == 0 and not run.stderr, run
    results.append(dict(test='regular-zsh-fallback', status=0))
source = (ROOT / 'native/test-completion-header-zle.py').read_text()
source = source.replace("ROOT=Path(__file__).resolve().parents[1]", 'ROOT=Path(' + repr(str(ROOT)) + ')')
source = source.replace('''if [[ $COMP_CASE == control-* ]]; then
 autoload -Uz compinit
 compinit -i -d "$HOME/dump"
elif [[ $COMP_CASE == candidate-* ]]; then
 functions[compinit]="$(< $WSH_COMPINIT_PROTOTYPE)"
 compinit -i -d "$HOME/dump"
fi''', '''if [[ $COMP_CASE == control-* ]]; then
 functions[compinit]="$(< $WSH_COMPINIT_PROTOTYPE)"
 compinit -i -d "$HOME/dump"
elif [[ $COMP_CASE == candidate-* ]]; then
 autoload -Uz compinit
 compinit -i -d "$HOME/dump"
fi''')
harness = OUT / 'zle.py'
harness.write_text(source)
run = subprocess.run([sys.executable, harness, BUNDLE, fixture, OUT / 'zle', MODE], capture_output=True)
(OUT / (MODE + '.stdout')).write_bytes(run.stdout)
(OUT / (MODE + '.stderr')).write_bytes(run.stderr)
results.append(dict(test='installed-zle-' + MODE, status=run.returncode))
(OUT / (MODE + '-results.json')).write_text(json.dumps(results, indent=2) + '\n')
assert run.returncode == 0, run.stderr
print(run.stdout.decode(), end='')
