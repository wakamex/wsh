#!/usr/bin/env python3
"""History substring search skips other shells' commands while set-local-history is on."""
import os
from pathlib import Path
import pty
import select
import signal
import sys
import tempfile
import time

BINARY = Path(sys.argv[1]).resolve()
PROMPT = b'\x1b]133;B'
RC = '''setopt share_history
_report() { print -r -- "BUFFER=[$BUFFER]" >> ~/buffers; BUFFER=; zle .accept-line }
zle -N _report; bindkey '^G' _report
_local() { zle set-local-history 1 }
zle -N _local; bindkey '^T' _local
'''


class Shell:
    def __init__(self, home):
        self.output = bytearray()
        environment = {'HOME': str(home), 'ZDOTDIR': str(home), 'PATH': '/usr/bin:/bin', 'TERM': 'xterm-256color',
                       'LC_ALL': 'C.UTF-8', 'WSH_THEME': 'minimal', 'WAKTERM_SHELL_SKIP_PANE_HISTORY': '1'}
        self.pid, self.fd = pty.fork()
        if not self.pid:
            os.chdir(home)
            os.execve(BINARY, [str(BINARY), '-di'], environment)
        self.wait(PROMPT)

    def wait(self, token, timeout=15):
        deadline = time.monotonic() + timeout
        while token not in self.output:
            assert time.monotonic() < deadline, bytes(self.output[-500:])
            if select.select([self.fd], [], [], .05)[0]:
                self.output.extend(os.read(self.fd, 65536))

    def type(self, data, token=PROMPT):
        del self.output[:]
        os.write(self.fd, data)
        self.wait(token)

    def close(self):
        os.kill(self.pid, signal.SIGKILL)
        os.waitpid(self.pid, 0)


with tempfile.TemporaryDirectory(prefix='wsh-local-search-') as directory:
    home = Path(directory)
    (home / '.zshrc').write_text(RC)
    first, second = Shell(home), Shell(home)
    try:
        second.type(b': LOCAL_SEARCH_OWN\n')
        first.type(b': LOCAL_SEARCH_OTHER\n')
        second.type(b':\n')  # imports the other shell's command
        second.type(b'LOCAL_SEARCH_OT\x1b[A\x07')
        second.type(b'\x14LOCAL_SEARCH_O\x1b[A\x07')
    finally:
        first.close()
        second.close()
    buffers = (home / 'buffers').read_text().splitlines()
    assert buffers == ['BUFFER=[: LOCAL_SEARCH_OTHER]', 'BUFFER=[: LOCAL_SEARCH_OWN]'], buffers
print('PASS: history substring search finds other shells\' commands, and only local ones in local mode')
