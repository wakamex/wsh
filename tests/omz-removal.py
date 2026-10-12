#!/usr/bin/env python3
"""Check that removing the Oh My Zsh line changes only behavior Wsh chose not to adopt.

Usage: omz-removal.py WSH OMZ OUTPUT

Starts interactive Wsh twice in a pseudo-terminal from the same .zshrc, with and without
`source $ZSH/oh-my-zsh.sh`, and compares options, key bindings, completion styles, aliases,
functions, widgets, hooks and exported parameters. Every difference must match an entry in
omz-removal-allowed.json, which mirrors the "left to user files" and "not adopted" lists in
FEATURES.md.
"""
from fnmatch import fnmatchcase
import json
import os
from pathlib import Path
import pty
import select
import shlex
import signal
import sys
import time

# Wsh finds its resources from the path it was started by, so keep bin/wsh unresolved.
wsh = Path(sys.argv[1]).absolute()
omz, output = [Path(p).resolve() for p in sys.argv[2:]]
output.mkdir(parents=True, exist_ok=True)
allowed = json.loads(Path(__file__).with_name('omz-removal-allowed.json').read_text())

CAPTURE = r'''
{
  local k v m h
  for k in ${(ko)options}; do print -r -- "option:$k"$'\t'"$options[$k]"; done
  for m in main vicmd; do
    bindkey -M $m | while read -r v; do print -r -- "key:$m:${v% *}"$'\t'"${v##* }"; done
  done
  print -r -- "completion:initialized"$'\t'"${+functions[compdef]}"
  for k in fg bg fg_bold reset_color; do print -r -- "colors:$k"$'\t'"${+parameters[$k]}"; done
  local -a w
  zstyle -L | while read -r v; do
    w=(${(z)${v#zstyle }})
    [[ $w[1] == -e ]] && k="$w[1,3]" || k="$w[1,2]"
    print -r -- "style:$k"$'\t'"$v"
  done
  for k in ${(ko)aliases}; do print -r -- "alias:$k"$'\t'"${(q)aliases[$k]}"; done
  for k in ${(ko)galiases}; do print -r -- "global-alias:$k"$'\t'"${(q)galiases[$k]}"; done
  for k in ${(ko)functions}; do print -r -- "function:$k"$'\t'"${functions_source[$k]}"; done
  for k in ${(ko)widgets}; do print -r -- "widget:$k"$'\t'"$widgets[$k]"; done
  for h in chpwd precmd preexec periodic zshaddhistory zshexit; do
    for k in ${(P)${:-${h}_functions}}; do print -r -- "hook:$h:$k"$'\t'1; done
  done
  for k in ${(ko)parameters[(R)*export*]} HISTFILE HISTSIZE SAVEHIST WORDCHARS KEYTIMEOUT; do
    print -r -- "parameter:$k"$'\t'"${(q)${(P)k}}"
  done
} > $HOME/capture.txt
print -r -- $'\x1eCAPTURED\x1f'
'''


def capture(name, with_omz, last=''):
    home = output / name
    home.mkdir(exist_ok=True)
    config = f'ZSH={shlex.quote(str(omz))}\nZSH_THEME=""\nplugins=()\nzstyle ":omz:update" mode disabled\n'
    if with_omz:
        config += 'source "$ZSH/oh-my-zsh.sh"\n'
    (home / '.zshrc').write_text(config + last)
    (home / 'capture.zsh').write_text(CAPTURE)
    env = dict(PATH='/usr/bin:/bin', HOME=str(home), ZDOTDIR=str(home), TERM='xterm-256color', LC_ALL='C.UTF-8', WSH_THEME='')
    pid, fd = pty.fork()
    if not pid:
        os.chdir(home)
        os.execve(wsh, ['wsh', '-di'], env)
    data = bytearray()

    def wait(marker):
        end = time.monotonic() + 20
        while marker not in data:
            assert time.monotonic() < end, bytes(data[-1500:])
            if select.select([fd], [], [], .05)[0]:
                data.extend(os.read(fd, 65536))
    try:
        wait(b'\x1b]133;B')
        os.write(fd, b'source $HOME/capture.zsh\n')
        wait(b'\x1eCAPTURED\x1f')
    finally:
        (home / 'transcript.bin').write_bytes(data)
        assert b'Wsh integration unavailable' not in data, name
        os.kill(pid, signal.SIGHUP)
        os.waitpid(pid, 0)
        os.close(fd)
    state = {}
    for line in (home / 'capture.txt').read_text(errors='replace').splitlines():
        key, _, value = line.partition('\t')
        # Each run has its own home directory.
        state[key.replace(str(home), '~')] = value.replace(str(home), '~')
    # Autosuggestions wrap whichever widgets exist; compare what they wrap.
    for key in [key for key in state if key.startswith('widget:autosuggest-orig-')]:
        state['widget:' + key.split('-', 3)[3].removeprefix('user:')] = state.pop(key)
    for key in list(state):
        kind, _, name = key.partition(':')
        value = state[key]
        # The completion system's own functions, widgets and keys are covered by
        # completion:initialized, and builtin widgets by the styles and keys that use them.
        if (kind == 'function' and (name.startswith('_') or name in COMPLETION_FUNCTIONS)
                or kind == 'widget' and (value == 'builtin' or value.startswith('completion:'))
                or kind == 'key' and value.startswith('_')
                or key == 'style:zle-line-finish widgets'):
            del state[key]
    return state


COMPLETION_FUNCTIONS = {'compinit', 'compdef', 'compdump', 'compaudit', 'compinstall', 'bashcompinit'}
differences, unexplained, used = [], [], set()
# Oh My Zsh binds the emacs and vi keymaps separately, so compare a session of each kind. It
# selects emacs itself, so a vi user's `bindkey -v` follows it.
for keymap, last in (('emacs', ''), ('vi', 'bindkey -v\n')):
    with_omz, without = capture(keymap + '-with', True, last), capture(keymap + '-without', False, last)
    for key in sorted(with_omz.keys() | without.keys()):
        before, after = with_omz.get(key), without.get(key)
        if before == after:
            continue
        label = f'{keymap} {key}' if key.startswith('key:') else key
        if any(row['key'] == label for row in differences):
            continue
        reason = None
        # A function defined in the Oh My Zsh checkout is Oh My Zsh's own.
        if key.startswith('function:') and after is None and before.startswith(str(omz)):
            reason = "Oh My Zsh's own commands and prompt helpers"
        for entry in allowed:
            if reason is None and fnmatchcase(label, entry['key']) and entry.get('without', after) == after:
                reason = entry['reason']
                used.add(entry['key'])
        row = dict(key=label, with_omz=before, without_omz=after, reason=reason)
        differences.append(row)
        if reason is None:
            unexplained.append(row)
(output / 'differences.json').write_text(json.dumps(differences, indent=2) + '\n')
unused = [entry['key'] for entry in allowed if entry['key'] not in used]
for row in unexplained:
    print(f"UNEXPLAINED {row['key']}: {row['with_omz']!r} -> {row['without_omz']!r}"[:200])
for key in unused:
    print(f'UNUSED allowance: {key}')
if unexplained or unused:
    raise SystemExit(f'FAIL: {len(unexplained)} of {len(differences)} differences are not allowed; {len(unused)} allowances unused')
print(f'PASS: removing Oh My Zsh changes only {len(differences)} allowed items')
