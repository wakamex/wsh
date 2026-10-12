#!/usr/bin/env python3
"""Check Wsh's interactive defaults and that user startup files override them.

Usage: interactive-defaults.py WSH OUTPUT
"""
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import time

# Wsh finds its resources from the path it was started by, so keep bin/wsh unresolved.
wsh = Path(sys.argv[1]).absolute()
output = Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=True)
checks = 0


def check(name, condition, detail=''):
    global checks
    assert condition, f'{name}: {detail}'
    checks += 1


class Shell:
    def __init__(self, name, config, env=None):
        self.home = output / name
        self.home.mkdir(exist_ok=True)
        (self.home / 'Documents').mkdir(exist_ok=True)
        (self.home / '.zshrc').write_text(config)
        environment = dict(PATH='/usr/bin:/bin', HOME=str(self.home), ZDOTDIR=str(self.home), TERM='xterm-256color',
                           LC_ALL='C.UTF-8', WSH_THEME='', **(env or {}))
        self.pid, self.fd = pty.fork()
        if not self.pid:
            os.chdir(self.home)
            os.execve(wsh, ['wsh', '-di'], environment)
        self.data = bytearray()
        self.wait(b'\x1b]133;B')
        assert b'Wsh integration unavailable' not in self.data, name

    def wait(self, marker, offset=0):
        end = time.monotonic() + 20
        while marker not in self.data[offset:]:
            assert time.monotonic() < end, bytes(self.data[-1500:])
            if select.select([self.fd], [], [], .05)[0]:
                self.data.extend(os.read(self.fd, 65536))

    def keys(self, data):
        """Type keys ending in Enter, then wait for the following prompt."""
        offset = len(self.data)
        os.write(self.fd, data)
        self.wait(b'\x1b]133;D', offset)
        self.wait(b'\x1b]133;B', offset)

    def value(self, expression):
        (self.home / 'value').unlink(missing_ok=True)
        self.keys(f'print -r -- {expression} > $HOME/value\n'.encode())
        return (self.home / 'value').read_text().rstrip('\n')

    def read(self, name):
        path = self.home / name
        return path.read_text().rstrip('\n') if path.exists() else None

    def close(self):
        (self.home / 'transcript.bin').write_bytes(self.data)
        os.kill(self.pid, signal.SIGHUP)
        os.waitpid(self.pid, 0)
        os.close(self.fd)


def typed_keys(shell, label):
    """Editing keys that work the same in the emacs and vi insert keymaps."""
    for name, home in (('csi', b'\x1b[H'), ('ss3', b'\x1bOH'), ('tilde', b'\x1b[1~')):
        shell.keys(b'Xprint ok > $HOME/home-' + name.encode() + home + b'\x1b[3~\n')
        check(f'{label}: Home ({name}) and Delete', shell.read('home-' + name) == 'ok', shell.read('home-' + name))
    for name, end in (('csi', b'\x1b[F'), ('ss3', b'\x1bOF'), ('tilde', b'\x1b[4~')):
        shell.keys(b'rint ok > $HOME/end-' + name.encode() + b'\x1b[H' + end + b'\x1b[H' + b'p\n')
        check(f'{label}: End ({name})', shell.read('end-' + name) == 'ok', shell.read('end-' + name))
    # Ctrl+Left moves over one path component, so the X lands before "lib".
    shell.keys(b'print -r -- > $HOME/word /usr/lib\x1b[1;5DX\n')
    check(f'{label}: Ctrl+Left stops inside a path', shell.read('word') == '/usr/Xlib', shell.read('word'))
    shell.keys(b'print -r -- > $HOME/kill one two\x1b[1;5D\x1b[3;5~\n')
    check(f'{label}: Ctrl+Delete removes the next word', shell.read('kill') == 'one', shell.read('kill'))


# Defaults with an empty startup file.
shell = Shell('bare', '_mytool() { compadd alpha beta }\ncompdef _mytool mytool\nmytool() { print -r -- "$1" > $HOME/completed }\n')
try:
    check('completion initialized', shell.value('${+_comps}') == '1')
    check('queued compdef applied', shell.value('$_comps[mytool]') == '_mytool')
    check('compdef queue removed', shell.value('${+_wsh_compdef_queue}') == '0')
    shell.keys(b'mytool al\t\n')
    check('Tab completes through a queued compdef', shell.read('completed') == 'alpha', shell.read('completed'))
    shell.keys(b'cd doc\t\n')
    check('completion ignores case', shell.value('$PWD') == str(shell.home / 'Documents'))
    shell.keys(b'cd ~\n')
    typed_keys(shell, 'emacs')
    shell.keys(b'print -r -- /usr/lib\x17bin > $HOME/ctrl-w\n')
    check('Ctrl+W stops at a slash', shell.read('ctrl-w') == '/usr/bin', shell.read('ctrl-w'))
    shell.keys(b'print ok > $HOME/comment # a comment\n')
    check('comments at the prompt', shell.read('comment') == 'ok', shell.read('comment'))
    shell.keys(b' print secret\n')
    shell.keys(b'true\n')
    shell.keys(b'fc -ln 1 > $HOME/history-list\n')
    check('space-prefixed commands stay out of history', 'secret' not in shell.read('history-list'), shell.read('history-list'))
    shell.keys(b'print first last\n')
    shell.keys(b'print -r -- !$ > $HOME/magic\n')
    # With hist_verify on, an unexpanded reference would need a second Enter to run.
    check('Space expands history references', shell.read('magic') == 'last', shell.read('magic'))
    options = shell.value('"$options[alwaystoend] $options[completeinword] $options[flowcontrol] $options[histverify] $options[histignoredups] $options[histexpiredupsfirst] $options[longlistjobs] $options[promptsubst]"')
    check('options', options == 'on on off on on on on on', options)
    check('parameters', shell.value('"$HISTSIZE $SAVEHIST $PAGER ${#WORDCHARS} ${+fg[red]} ${+reset_color}"') == '50000 10000 less 0 1 1')
    table = 'print -rl -- ${(qkv)color} ${(qkv)colour} ${(qkv)fg} ${(qkv)bg} ${(qkv)fg_bold} ${(qkv)bg_bold} ${(qkv)fg_no_bold} ${(qkv)bg_no_bold} ${(q)reset_color} ${(q)bold_color}'
    shell.keys(f'{table} > $HOME/colors-default; colors; {table} > $HOME/colors-function\n'.encode())
    # Keys and values alternate; the order within each array depends on how it was filled.
    pairs = [sorted(zip(lines[::2], lines[1::2])) for lines in (shell.read(name).splitlines() for name in ('colors-default', 'colors-function'))]
    check('colour arrays match the colors function', pairs[0] == pairs[1] and len(pairs[0]) > 100)
    check('completion styles', 'select' in shell.value('"$(zstyle -L \':completion:\\*\' menu)"'))
    if Path('/usr/bin/dircolors').exists():
        check('LS_COLORS set when the environment has none', shell.value('${+LS_COLORS}') == '1')
finally:
    shell.close()

# User startup files and the environment win over every kind of default.
shell = Shell('override', '''unsetopt interactive_comments hist_verify
setopt flow_control
WORDCHARS='/'
HISTSIZE=77
bindkey '^[[3~' beginning-of-line
zstyle ':completion:*' menu no
zstyle ':completion:*' matcher-list ''
''', env=dict(PAGER='cat', LS_COLORS='di=01;31'))
try:
    options = shell.value('"$options[interactivecomments] $options[histverify] $options[flowcontrol]"')
    check('user options kept', options == 'off off on', options)
    check('user parameters kept', shell.value('"$WORDCHARS $HISTSIZE $PAGER $LS_COLORS"') == '/ 77 cat di=01;31')
    check('user binding kept', shell.value('"$(bindkey \'^[[3~\')"').endswith('beginning-of-line'))
    styles = shell.value('"$(zstyle -L \':completion:\\*\' menu) $(zstyle -L \':completion:\\*\' matcher-list)"')
    check('user styles kept', 'menu no' in styles and 'lower' not in styles, styles)
finally:
    shell.close()

# A user's own completion setup is left alone, and earlier compdef calls still apply.
shell = Shell('user-completion', '_early() { compadd early }\ncompdef _early early\nautoload -Uz compinit\ncompinit -d $HOME/user-dump\n')
try:
    check('user completion kept', shell.value('$_comps[early]') == '_early')
    check('user dump used', (shell.home / 'user-dump').exists() and not (shell.home / '.zcompdump').exists())
finally:
    shell.close()

shell = Shell('no-completion', 'WSH_DISABLE_COMPLETION=1\ncompdef _x x\n')
try:
    check('completion can be turned off', shell.value('"${+_comps} ${+functions[compdef]}"') == '0 0')
    check('no startup error without completion', b'command not found' not in shell.data, bytes(shell.data[-500:]))
finally:
    shell.close()

shell = Shell('vi', 'bindkey -v\n')
try:
    typed_keys(shell, 'vi')
finally:
    shell.close()

# Scripts and shells without startup files get none of the defaults.
home = output / 'bare'
environment = dict(PATH='/usr/bin:/bin', HOME=str(home), ZDOTDIR=str(home))
probe = 'print -r -- "$options[interactivecomments] ${+functions[compdef]} ${+PAGER} ${+fg} $(( ${#WORDCHARS} > 0 ))"'
value = subprocess.check_output([wsh, '-dc', probe], env=environment, text=True).strip()
check('non-interactive shell unchanged', value == 'off 0 0 0 1', value)
value = subprocess.check_output([wsh, '-dfic', probe], env=environment, text=True, stderr=subprocess.DEVNULL).strip()
check('shell without startup files unchanged', value == 'off 0 0 0 1', value)
print(f'PASS: {checks} interactive default, override and completion checks')
