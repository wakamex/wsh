#!/usr/bin/env python3
"""Exercise every admitted upstream snapshot through actual interactive startup."""
import json
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
bundle, output = [Path(p).resolve() for p in sys.argv[1:]]
output.mkdir(parents=True, exist_ok=True)
catalog = json.loads((ROOT / 'third_party/plugin-catalog/catalog.json').read_text())
parameters = {'autosuggestions': 'AUTOSUGGESTIONS', 'history': 'HISTORY_SUBSTRING_SEARCH', 'syntax': 'SYNTAX_HIGHLIGHTING', 'directory': 'DIRECTORY_JUMP', 'git-prompt': 'GIT_PROMPT'}
rows = []
for entry in catalog['entries']:
    component = entry['component']
    variants = ['exact', 'modified', 'override']
    if component == 'autosuggestions':
        variants += ['active', 'disabled']
        if entry['version'] != 'v0.5.2':
            variants += ['lifecycle-opt-in']
    if len(entry['files']) == 2:
        variants += ['modified-second']
    for variant in variants:
        home = output / component / entry['version'] / variant
        home.mkdir(parents=True, exist_ok=True)
        paths = []
        if component == 'syntax':
            shutil.copytree(ROOT / 'third_party/zsh-syntax-highlighting', home / 'plugin', dirs_exist_ok=True)
        for index, record in enumerate(entry['files']):
            relative = record['upstream_path'] if component == 'syntax' else Path(record['upstream_path']).name
            target = home / 'plugin' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / record['source']).read_bytes() + (b'\n# modified fixture\n' if (variant == 'modified' and index == 0) or (variant == 'modified-second' and index == 1) else b''))
            paths.append(target)
        config = 'PROMPT="CATALOG> "\nHISTSIZE=100\nSAVEHIST=0\nZSHZ_DATA=$HOME/jump-data\n'
        config += 'source ' + shlex.quote(str(paths[0])) + '\n'
        config += 'ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE=fg=blue\nWSH_AUTOSUGGEST_ASYNC=0\nHISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND=fg=blue\n'
        override = {'autosuggestions': '_zsh_autosuggest_widget_accept', 'history': '_history-substring-search-begin', 'syntax': '_zsh_highlight_highlighter_main_predicate', 'directory': '_zshz_precmd', 'git-prompt': 'precmd_update_git_vars'}[component]
        if variant == 'override':
            config += override + '() { :; }\n'
        if variant == 'lifecycle-opt-in':
            config += "ZSH_AUTOSUGGEST_IGNORE_WIDGETS=('zle-line-finish' 'zle-line-pre-redraw' 'zle-keymap-select' 'zle-isearch-update' 'zle-isearch-exit' 'zle-history-line-set')\n_catalog_init() { (( ++LIFECYCLE_COUNT )); }\nzle -N zle-line-init _catalog_init\nzle-custom() { BUFFER+='CUSTOM'; }\nzle -N zle-custom\nbindkey '^X' zle-custom\n"
        if variant == 'active':
            config += '_zsh_autosuggest_start\n'
        if variant == 'disabled':
            config += 'WSH_DISABLE_AUTOSUGGESTIONS=1\n'
        config += '''print -s -- 'echo needle catalog'
_catalog_observe() { print -nr -- $'\x1eEDITOR:'"$BUFFER|$POSTDISPLAY"$'\x1f'; }
zle -N _catalog_observe
bindkey '^T' _catalog_observe
'''
        if component == 'history':
            config += "bindkey '^P' history-substring-search-up\n"
        (home / '.zshrc').write_text(config)
        env = dict(PATH='/usr/bin:/bin', HOME=str(home), ZDOTDIR=str(home), TERM='xterm-256color', LC_ALL='C.UTF-8', WSH_THEME='minimal' if component == 'git-prompt' else '')
        pid, fd = pty.fork()
        if not pid:
            os.chdir(home)
            os.execve(bundle / 'bin/wsh', ['wsh', '-di'], env)
        data = bytearray()
        def wait(marker, offset=0):
            deadline = time.monotonic() + 10
            while marker not in data[offset:]:
                assert time.monotonic() < deadline, (component, entry['version'], variant, bytes(data[-1200:]))
                if select.select([fd], [], [], .05)[0]:
                    data.extend(os.read(fd, 65536))
        try:
            wait(b'\x1b]133;B')
            offset = len(data)
            command = "print -r -- $'\\x1eSTATE:'\"$WSH_" + parameters[component] + "_OWNER|$ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE|$HISTORY_SUBSTRING_SEARCH_HIGHLIGHT_FOUND\"$'\\x1f'\n"
            os.write(fd, command.encode())
            wait(b'\x1eSTATE:', offset)
            start = data.index(b'\x1eSTATE:', offset) + 7
            wait(b'\x1f', start)
            state = bytes(data[start:data.index(b'\x1f', start)]).decode()
            expected = ('external-exact' if component == 'syntax' else 'wsh') if variant in ('exact', 'lifecycle-opt-in') else 'external-active' if variant == 'active' else 'disabled' if variant == 'disabled' else 'external' if component == 'directory' else 'external-unknown'
            assert state == expected + '|fg=blue|fg=blue', (component, entry['version'], variant, state)
            wait(b'\x1b]133;B', offset)
            if variant == 'lifecycle-opt-in':
                offset = len(data)
                os.write(fd, b"[[ $widgets[zle-line-init] == user:_zsh_autosuggest_bound_* && $LIFECYCLE_COUNT -gt 0 && $#ZSH_AUTOSUGGEST_IGNORE_WIDGETS == 6 ]] && print -r -- $'\\x1eHOOK-OPT-IN\\x1f'\n")
                wait(b'\x1eHOOK-OPT-IN\x1f', offset)
                wait(b'\x1b]133;B', offset)
            if variant in ('exact', 'lifecycle-opt-in') and component in ('autosuggestions', 'history'):
                offset = len(data)
                if component == 'autosuggestions':
                    os.write(fd, b'echo need')
                    time.sleep(.05)
                    os.write(fd, b'\x14')
                    wait(b'\x1eEDITOR:echo need|le catalog\x1f', offset)
                    offset = len(data)
                    os.write(fd, b'\x1b[C\x14')
                    wait(b'\x1eEDITOR:echo needle catalog|\x1f', offset)
                else:
                    os.write(fd, b'needle\x10\x14')
                    wait(b'\x1eEDITOR:echo needle catalog|', offset)
            if variant == 'lifecycle-opt-in':
                offset = len(data)
                os.write(fd, b'\x18\x14')
                wait(b'\x1eEDITOR:echo needle catalogCUSTOM|', offset)
            rows.append(dict(component=component, version=entry['version'], variant=variant, state=state, passed=True))
            (output / 'results.json').write_text(json.dumps(rows, indent=2) + '\n')
        finally:
            (home / 'transcript.bin').write_bytes(data)
            os.kill(pid, signal.SIGHUP)
            os.waitpid(pid, 0)
            os.close(fd)
print('PASS:', len(catalog['entries']), 'upstream snapshots;', len(rows), 'handoff, customization and editor cases')
