#!/usr/bin/env python3
"""Exercise ZLE's real region setter/getter, including neutral-style ownership."""
import json
import os
from pathlib import Path
import pty
import select
import signal
import sys
import time

binary = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
config = r'''
PROMPT='ROUNDTRIP> '
_probe() {
 local value
 for value in '0 1 fg=green memo=probe' '0 1 none memo=probe' '0 1 none, memo=probe' '0 1 none,layer=4 memo=probe' '0 1 bold,none memo=probe'; do
  region_highlight=("$value")
  local first=$region_highlight[1]
  region_highlight=("${region_highlight[@]}")
  print -nr -- $'\x1eROW:'"$value|$first|$region_highlight[1]"$'\x1f'
 done
 region_highlight=()
 print -nr -- $'\x1eDONE\x1f'
}
zle -N _probe
bindkey '^T' _probe
'''
(out / '.zshrc').write_text(config)
env = dict(PATH='/usr/bin:/bin', HOME=str(out), ZDOTDIR=str(out), TERM='xterm-256color', LC_ALL='C.UTF-8', WSH_THEME='', WSH_DISABLE_AUTOSUGGESTIONS='1', WSH_DISABLE_SYNTAX_HIGHLIGHTING='1', WSH_DISABLE_HISTORY_SUBSTRING_SEARCH='1', WSH_DISABLE_DIRECTORY_JUMP='1')
env.update({k: v for k, v in os.environ.items() if k.endswith('SAN_OPTIONS')})
pid, fd = pty.fork()
if not pid:
    os.execve(binary, [str(binary), '-di'], env)
data = bytearray()
def wait(marker):
    end = time.monotonic() + 10
    while marker not in data:
        assert time.monotonic() < end, bytes(data[-1000:])
        if select.select([fd], [], [], .05)[0]:
            data.extend(os.read(fd, 65536))
try:
    wait(b'\x1b]133;B')
    os.write(fd, b'\x14')
    wait(b'\x1eDONE\x1f')
    rows = []
    for piece in bytes(data).split(b'\x1eROW:')[1:]:
        given, first, second = piece.split(b'\x1f')[0].decode().split('|')
        expected = given.replace('none, memo=', 'none memo=').replace('bold,none', 'bold')
        rows.append(dict(input=given, expected=expected, first=first, second=second, stable=first == second, memo_preserved='memo=probe' in second, correct=first == second == expected))
    (out / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps(rows, indent=2))
    passed = len(rows) == 5 and all(r['correct'] for r in rows)
    assert passed == ('--expect-failure' not in sys.argv)
finally:
    (out / 'transcript.bin').write_bytes(data)
    os.kill(pid, signal.SIGHUP)
    os.waitpid(pid, 0)
    os.close(fd)
