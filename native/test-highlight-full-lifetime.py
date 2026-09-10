#!/usr/bin/env python3
"""Hold a real shell between redraw batches and check retained memory growth."""
import json
import os
from pathlib import Path
import select
import shlex
import subprocess
import sys
binary, source, out = map(lambda s: Path(s).resolve(), sys.argv[1:])
out.mkdir(parents=True, exist_ok=True)
script = out / 'lifetime.zsh'
script.write_text(f'''source {shlex.quote(str(source))}
_run() {{
 local BUFFER='' PREBUFFER='' WIDGET='' CONTEXT=''
 local -a region_highlight
 local -A zsyh_user_options=("${{(kv)options[@]}}")
 emulate -L zsh
 BUFFER='{'echo hello; ' * 100}'
 integer phase i
 for phase in 1 2 3; do
  for (( i=0; i<2000; i++ )); do
   region_highlight=()
   _zsh_highlight_highlighter_main_paint
  done
  print -r -- READY
  read -r REPLY
 done
}}
_run
''')
env = dict(PATH='/usr/bin:/bin', HOME=str(out), ZDOTDIR=str(out), LC_ALL='C.UTF-8', TERM='xterm-256color')
process = subprocess.Popen([binary, '-df', script], env=env, cwd=out, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
rss = []
try:
    for _ in range(3):
        assert select.select([process.stdout], [], [], 120)[0], 'redraw batch timed out'
        assert process.stdout.readline() == b'READY\n'
        status = Path(f'/proc/{process.pid}/status').read_text()
        rss.append(int(next(s for s in status.splitlines() if s.startswith('VmRSS:')).split()[1]))
        process.stdin.write(b'continue\n')
        process.stdin.flush()
    stdout, stderr = process.communicate(timeout=10)
    assert process.returncode == 0 and not stderr, (process.returncode, stderr)
finally:
    if process.poll() is None:
        process.kill()
        process.wait()
result = dict(redraws_per_batch=2000, rss_kib=rss, retained_growth_kib=rss[-1]-rss[0], maximum_growth_kib=8192)
(out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
assert result['retained_growth_kib'] <= result['maximum_growth_kib']
