#!/usr/bin/env python3
"""Compare actual styles for every editing prefix, using the original highlighter."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

binary, fixture, out = [Path(s).resolve() for s in sys.argv[1:]]
out.mkdir(parents=True, exist_ok=True)
home = out / 'home'
home.mkdir(exist_ok=True)
commands = [
    'echo "hello ${HOME} $(printf \'%s\' world)"; true',
    "a=( one 'two three' ); echo ${a[1]} > ./output",
    "if true; then for x in a b; do echo $x; done; fi",
    "echo `echo \\`printf 42\\``; echo $(( 1 + $(echo 2) ))",
    "sudo -u root env FOO=bar command -p printf %s *.zsh",
    "echo héllo 世界 'a\\b' $'a\\x41\\u03bb' ~/missing",
    "{ echo hi; } always { false; }; [[ a && b ]]",
    "aa --flag; loop; $cmd; $empty; echo global_alias",
    "echo <(printf x) =(echo y) ${x:-$(touch SHOULD_NOT_EXIST)}",
    "echo $(touch SHOULD_NOT_EXIST) `touch SHOULD_NOT_EXIST`",
]
buffers = list(dict.fromkeys(s[:i] for s in commands for i in range(1, len(s)+1)))
buffers += ['', 'echo \\', 'echo \x00x', 'echo \x1bx', 'echo\tfoo\n#comment', "echo '' \"\"", 'echo / ./ ../', '=does-not-exist']
modes = ['', 'setopt rcquotes', 'unsetopt multios', 'setopt globassign', 'setopt interactivecomments', 'setopt shwordsplit', 'setopt ignorebraces ignoreclosebraces']
rows = []
for mode_index, mode in enumerate(modes):
    outputs = {}
    for owner in ('control', 'candidate'):
        # NUL cannot be represented in a source file word; create it with Zsh quoting.
        quoted = [("'" + s.replace("'", "'\\''") + "'") if '\0' not in s else "$'echo \\0x'" for s in buffers]
        script = f'''source {shlex.quote(str(fixture / owner / 'zsh-syntax-highlighting.zsh'))}
ZSH_HIGHLIGHT_HIGHLIGHTERS=(main)
alias aa='echo' loop='loop'
alias -g global_alias='true'
cmd=echo empty=''
{mode}
_run() {{
 local BUFFER PREBUFFER='' WIDGET='' CONTEXT='' sample
 local -a region_highlight
 local -A zsyh_user_options=("${{(kv)options[@]}}")
 emulate -L zsh
 for sample in {' '.join(quoted)}; do
  BUFFER=$sample
  region_highlight=()
  _zsh_highlight_highlighter_main_paint
  print -r -- "${{(j:;:)${{(@qqqq)region_highlight}}}}"
 done
}}
_run
'''
        path = out / f'{mode_index}-{owner}.zsh'
        path.write_text(script)
        env = dict(PATH='/usr/bin:/bin', HOME=str(home), ZDOTDIR=str(home), LC_ALL='C.UTF-8', TERM='xterm-256color')
        env.update({k: v for k, v in os.environ.items() if k.endswith('SAN_OPTIONS')})
        run = subprocess.run([binary, '-df', path], cwd=home, env=env, capture_output=True, timeout=90)
        (out / f'{mode_index}-{owner}.stdout').write_bytes(run.stdout)
        (out / f'{mode_index}-{owner}.stderr').write_bytes(run.stderr)
        assert run.returncode == 0 and not run.stderr, (owner, mode, run.returncode, run.stderr[-2000:])
        outputs[owner] = run.stdout.decode().splitlines()
        assert len(outputs[owner]) == len(buffers), (owner, len(outputs[owner]), len(buffers))
    for i, buffer in enumerate(buffers):
        rows.append(dict(mode=mode, buffer=buffer, equal=outputs['control'][i] == outputs['candidate'][i], control=outputs['control'][i], candidate=outputs['candidate'][i]))
assert not (home / 'SHOULD_NOT_EXIST').exists(), 'highlighting executed input'
(out / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
summary = dict(cases=len(rows), equal=sum(r['equal'] for r in rows), input_executed=False)
(out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary))
raise SystemExit(any(not r['equal'] for r in rows))
