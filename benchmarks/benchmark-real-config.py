#!/usr/bin/env python3
"""Bounded real-configuration PTY experiment. Uses Python's standard library only."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import pty
import re
import select
import shlex
import shutil
import signal
import subprocess
import time

READY = b'\x1eWSH_MATRIX_READY\x1f'
ROOT = Path(__file__).resolve().parent.parent
PINS = {
    'omz': ('/var/tmp/wsh-real-config-2026-09-05/omz-source.git', '9112b53fa8b5ab556c7c893aa8be8a247ac512a0'),
    'wakamex': ('/code/wakamex-zsh-theme', '15c7c78214774408a6c007d0401415c7d0cded38'),
    'autosuggestions': ('/code/zsh-autosuggestions', '85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5'),
    'syntax': ('/code/zsh-syntax-highlighting', '2fc57d63067c18b1100ecdbf684fa5baf49459d1'),
}
CONFIGS = ['empty', 'plain', 'omz-none', 'robbyrussell', 'agnoster', 'wakamex', 'plugins', 'wakamex-plugins', 'actual']
OBSERVER = r'''
HISTFILE=$WSH_MATRIX_DIR/history
SAVEHIST=0
alias wsh_matrix_alias='print -r -- WSH_MATRIX_ALIAS_OK'
autoload -Uz add-zle-hook-widget add-zsh-hook
_wsh_matrix_ready() { print -nr -- $'\x1eWSH_MATRIX_READY\x1f'; }
_wsh_matrix_install() {
  zmodload zsh/zle
  add-zle-hook-widget zle-line-init _wsh_matrix_ready
  add-zsh-hook -d precmd _wsh_matrix_install
}
add-zsh-hook precmd _wsh_matrix_install
'''
STATE = r'''zmodload zsh/zleparameter; print -r -- $'\x1eMATRIX_STATE:'${WSH_HISTORY_SUBSTRING_SEARCH_OWNER:-external}:${WSH_AUTOSUGGESTIONS_OWNER:-external}:${WSH_SYNTAX_HIGHLIGHTING_OWNER:-external}:${WSH_RUNTIME_READY:-0}:${#${(M)precmd_functions:#_wsh_runtime_precmd}}:${#${(M)preexec_functions:#_wsh_runtime_preexec}}:${#${(M)zshexit_functions:#_wsh_runtime_stop}}:${+widgets[history-substring-search-up]}:${+functions[_zsh_autosuggest_start]}:${+ZSH_HIGHLIGHT_VERSION}:${+_comps}:${+aliases[g]}:${+functions[sdk]}:${+functions[nvm]}:${+functions[fnm]}:${(j:,:)precmd_functions}:${(j:,:)preexec_functions}:${(j:,:)zshexit_functions}:$'\x1f' '''

def run(argv, **kwargs):
    return subprocess.check_output([str(x) for x in argv], **kwargs)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive(name, dest):
    dest.mkdir(parents=True, exist_ok=True)
    source, revision = PINS[name]
    data = run(['git', '-C', source, 'archive', revision])
    subprocess.run(['tar', '-xf', '-', '-C', str(dest)], input=data, check=True)


def prepare(work, bundle, manager):
    if (work / 'prepared.json').exists():
        return json.loads((work / 'prepared.json').read_text())
    work.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(work, 0o700)
    actual_home = Path.home()
    snapshots = work / 'actual-startup'
    snapshots.mkdir(exist_ok=True)
    identities = {}
    for name in ['.zshenv', '.zprofile', '.zshrc', '.zlogin', '.zlogout']:
        source = actual_home / name
        if source.exists():
            shutil.copy2(source, snapshots / name)
            identities[name] = digest(source)
    # Private retained source identities, including installed custom theme/plugin bytes.
    dependencies = {}
    for base in ['.oh-my-zsh', '.sdkman/src', '.sdkman/bin', 'defi']:
        directory = actual_home / base
        if directory.exists():
            for source in directory.rglob('*'):
                if source.is_file() and source.suffix in ('.sh', '.zsh', '.zsh-theme', '.plugin.zsh'):
                    dependencies[str(source.relative_to(actual_home))] = digest(source)
    for name in ['.nvm/nvm.sh', 'defi/aliases', '.cargo/env', '.deno/env', '.bun/_bun', '.sdkman/etc/config']:
        source = actual_home / name
        if source.is_file():
            dependencies[name] = digest(source)
    (work / 'private-dependencies.json').write_text(json.dumps(dependencies, indent=2, sort_keys=True) + '\n')
    omz = work / 'omz'
    archive('omz', omz)
    archive('wakamex', omz / 'custom/themes')
    archive('autosuggestions', omz / 'custom/plugins/zsh-autosuggestions')
    archive('syntax', omz / 'custom/plugins/zsh-syntax-highlighting')
    fixture = work / 'fixture'
    fixture.mkdir()
    run(['git', '-C', fixture, 'init', '-q', '-b', 'main'])
    for i in range(1000):
        (fixture / f'file-{i}').write_text(f'{i}\n')
    (fixture / 'wsh_completion_unique').write_text('completion fixture\n')
    run(['git', '-C', fixture, 'add', '.'])
    run(['git', '-C', fixture, '-c', 'user.name=Wsh matrix', '-c', 'user.email=matrix@wsh.invalid', 'commit', '-qm', 'seed'])
    run([manager, 'bundle', 'activate', bundle, '--state-root', work / 'state'])
    zversion = json.loads((bundle / 'manifest.json').read_text())['zsh']['version']
    for config in CONFIGS:
        for variant in ['direct', 'normal', 'profile', 'functions']:
            directory = work / config / variant
            directory.mkdir(parents=True)
            prefix = f'module_path=({shlex.quote(str(bundle / "lib/zsh" / zversion))} $module_path)\nfpath=({shlex.quote(str(bundle / "share/zsh" / zversion / "functions"))} $fpath)\ntypeset -ga .term.extensions=(-query)\nZSH_COMPDUMP=$WSH_MATRIX_DIR/.zcompdump\nZSH_CACHE_DIR=$WSH_MATRIX_DIR/cache\n'
            env = (snapshots / '.zshenv').read_text() if config == 'actual' and (snapshots / '.zshenv').exists() else ''
            (directory / '.zshenv').write_text(prefix + env + '\n')
            if config == 'actual':
                rc = (snapshots / '.zshrc').read_text()
                for name in ['.zprofile', '.zlogin', '.zlogout']:
                    if (snapshots / name).exists():
                        shutil.copy2(snapshots / name, directory / name)
            elif config in ['empty', 'plain']:
                rc = '' if config == 'empty' else "alias wsh_plain_alias='print -r -- PLAIN_OK'\nsetopt auto_cd\n"
            else:
                theme = config if config in ['robbyrussell', 'agnoster', 'wakamex'] else 'wakamex' if config == 'wakamex-plugins' else ''
                plugins = 'history-substring-search zsh-autosuggestions zsh-syntax-highlighting' if config in ['plugins', 'wakamex-plugins'] else ''
                rc = f'export ZSH={shlex.quote(str(omz))}\nZSH_THEME={shlex.quote(theme)}\nplugins=({plugins})\nDISABLE_AUTO_UPDATE=true\nDISABLE_AUTO_TITLE=true\nZSH_DISABLE_COMPFIX=true\nzstyle ":omz:update" mode disabled\nsource $ZSH/oh-my-zsh.sh\n'
            (directory / '.zshrc').write_text(rc + '\n' + OBSERVER)
    metadata = {'actual_home': str(actual_home), 'startup_sha256': identities, 'dependencies_sha256': digest(work / 'private-dependencies.json'), 'pins': PINS, 'bundle': str(bundle), 'manager_sha256': digest(manager), 'bundle_sha256': digest(bundle / 'manifest.json'), 'zsh_sha256': digest(bundle / 'bin/zsh'), 'runtime_sha256': digest(bundle / 'bin/wsh-runtime'), 'fixture_tree': run(['git', '-C', fixture, 'rev-parse', 'HEAD^{tree}']).decode().strip()}
    (work / 'prepared.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata


class Shell:
    def __init__(self, work, bundle, manager, config, variant, label, trace=False):
        self.output = bytearray()
        self.work = work
        self.label = label
        self.closed = False
        env = {k: v for k, v in os.environ.items() if not k.startswith(('WSH_', 'WAKTERM_', 'ZSH_')) and k not in ['FPATH', 'ZDOTDIR', 'ZSH', 'ZSH_CUSTOM', 'TMUX', 'TMUX_PANE']}
        directory = work / config / variant
        env.update(HOME=str(Path.home() if config == 'actual' else directory), ZDOTDIR=str(directory), WSH_MATRIX_DIR=str(directory), WSH_STATE_ROOT=str(work / 'state'), TERM='xterm-256color', LC_ALL='C.UTF-8')
        if variant != 'direct':
            env['WSH_THEME'] = 'minimal'
        command = [str(bundle / 'bin/zsh'), '-di'] if variant == 'direct' else [str(manager)]
        if variant in ['profile', 'functions']:
            command += ['profile'] + (['--functions'] if variant == 'functions' else [])
        if trace:
            command = ['strace', '-f', '-qq', '-ttt', '-e', 'trace=process', '-o', str(work / f'{label}.strace')] + command
        self.started = time.monotonic_ns()
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.chdir(work / 'fixture')
            os.sched_setaffinity(0, {0})
            os.execvpe(command[0], command, env)
        try:
            self.read_until(READY)
        except Exception:
            self.save()
            os.kill(self.pid, signal.SIGHUP)
            os.waitpid(self.pid, 0)
            os.close(self.fd)
            raise
        self.first_ms = (time.monotonic_ns() - self.started) / 1e6

    def read_until(self, marker, offset=0, timeout=30):
        deadline = time.monotonic() + timeout
        while marker not in self.output[offset:]:
            if time.monotonic() >= deadline:
                self.save()
                raise RuntimeError(f'timeout: {self.label}, marker={marker!r}; private transcript retained')
            self.drain(min(0.1, max(0, deadline - time.monotonic())))
        if marker == READY:
            ready_end = self.output.index(READY, offset) + len(READY)
            self.read_until(b'\x1b]133;B', ready_end, timeout)
        return bytes(self.output[offset:])

    def drain(self, seconds):
        if select.select([self.fd], [], [], seconds)[0]:
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                data = b''
            if not data:
                raise RuntimeError(f'PTY exited: {self.label}; {len(self.output)} bytes retained')
            self.output.extend(data)
            if len(self.output) > 4 * 1024 * 1024:
                raise RuntimeError('bounded terminal output exceeded')

    def settle(self, seconds=0.15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.drain(max(0, min(0.02, deadline - time.monotonic())))

    def send(self, text):
        offset = len(self.output)
        os.write(self.fd, text.encode() if isinstance(text, str) else text)
        return offset

    def command(self, command, marker=READY):
        offset = self.send(command + '\n')
        return self.read_until(marker, offset)

    def save(self):
        (self.work / f'{self.label}.terminal').write_bytes(self.output)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.send('exit\n')
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                self.drain(0.02)
            except RuntimeError:
                break
            done, _ = os.waitpid(self.pid, os.WNOHANG)
            if done:
                self.pid = 0
                break
        self.save()
        if self.pid:
            done, _ = os.waitpid(self.pid, os.WNOHANG)
            if not done:
                os.kill(self.pid, signal.SIGHUP)
                os.waitpid(self.pid, 0)
        os.close(self.fd)


def correctness(shell, config, variant):
    shell.settle()
    shell.command('wsh_matrix_alias', b'WSH_MATRIX_ALIAS_OK\r\n')
    shell.read_until(READY, shell.output.rfind(b'WSH_MATRIX_ALIAS_OK\r\n'))
    offset = shell.send('print -r -- wsh_completion_\t')
    shell.settle(0.1)
    shell.send('\n')
    shell.read_until(b'wsh_completion_unique\r\n', offset)
    shell.read_until(READY, offset)
    shell.send(b'not_a_command')
    shell.settle(0.05)
    offset = shell.send(b'\x03')
    shell.read_until(READY, offset)
    data = shell.command(STATE)
    match = re.search(rb'\x1eMATRIX_STATE:([^\x1f]+)\x1f', data)
    if not match:
        raise RuntimeError(f'missing shell state: {shell.label}')
    state = match[1].decode().strip(':')
    fields = state.split(':')
    if variant != 'direct' and fields[3:7] != ['1', '1', '1', '1']:
        raise RuntimeError(f'Wsh runtime/hook ownership failure: {fields[:10]}')
    if variant != 'direct' and config in ['empty', 'plain', 'omz-none', 'robbyrussell', 'agnoster', 'wakamex', 'plugins', 'wakamex-plugins']:
        if fields[:2] != ['wsh', 'wsh'] or fields[2] not in ['wsh', 'external-exact']:
            raise RuntimeError(f'recognized plugin ownership failure: {fields[:3]}')
    if config == 'plain':
        shell.command('wsh_plain_alias', b'PLAIN_OK\r\n')
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['prepare', 'correctness', 'timing', 'diagnostics', 'control'])
    parser.add_argument('output', type=Path)
    parser.add_argument('work', type=Path, help='private retained working directory')
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--iterations', type=int, default=20)
    parser.add_argument('--configs', nargs='+', default=CONFIGS, choices=CONFIGS)
    args = parser.parse_args()
    work, bundle = args.work.resolve(), args.bundle.resolve()
    manager = ROOT / 'target/release/wsh'
    args.output.mkdir(parents=True, exist_ok=True)
    metadata = prepare(work, bundle, manager)
    if args.phase == 'prepare':
        public = dict(metadata)
        public.pop('actual_home')
        (args.output / 'inputs.json').write_text(json.dumps(public, indent=2) + '\n')
        return
    path = args.output / f'{args.phase}.tsv'
    if path.exists():
        raise SystemExit(f'refusing to replace {path}')
    with path.open('w') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(['config', 'variant', 'block', 'repetition', 'first_editable_ms', 'state_or_detail'])
        for config in args.configs:
            if args.phase != 'correctness' and not (work / f'{config}.correctness-passed').exists():
                raise SystemExit(f'correctness has not passed for {config}')
            print(f'{args.phase}: {config}', flush=True)
            if args.phase == 'diagnostics':
                warm = Shell(work, bundle, manager, config, 'functions', f'functions-warmup-{config}')
                try:
                    warm.settle()
                finally:
                    warm.close()
            if args.phase == 'timing':
                launches = [(v, 'warmup', i) for i in range(5) for v in ['direct', 'normal', 'profile']]
                launches += [(v, block, i) for block in ['forward', 'reverse'] for i in range(args.iterations) for v in (['direct', 'normal', 'profile'] if block == 'forward' else ['profile', 'normal', 'direct'])]
            elif args.phase == 'control':
                launches = [('normal', block, i) for i in range(args.iterations) for block in (['a', 'b'] if i % 2 == 0 else ['b', 'a'])]
            elif args.phase == 'correctness':
                launches = [(v, 'fresh-cache', 0) for v in ['direct', 'normal', 'profile']]
            else:
                launches = [(v, 'process', 0) for v in ['direct', 'normal']] + [('functions', 'functions', 0)]
            for variant, block, repetition in launches:
                label = f'{args.phase}-{config}-{variant}-{block}-{repetition}'
                shell = None
                try:
                    shell = Shell(work, bundle, manager, config, variant, label, trace=block == 'process')
                    detail = '-'
                    if args.phase == 'correctness':
                        detail = correctness(shell, config, variant)
                    elif args.phase == 'diagnostics':
                        shell.settle(0.4)
                        start = time.time()
                        shell.command(':')
                        shell.settle(0.4)
                        end = time.time()
                        detail = json.dumps({'transition_start': start, 'transition_end': end})
                    else:
                        shell.settle(0.08)
                    writer.writerow([config, variant, block, repetition, f'{shell.first_ms:.6f}', detail])
                    stream.flush()
                finally:
                    if shell:
                        shell.close()
            if args.phase == 'correctness':
                (work / f'{config}.correctness-passed').touch()


if __name__ == '__main__':
    main()
