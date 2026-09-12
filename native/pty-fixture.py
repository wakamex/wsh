"""Shared real-ZLE capture and transcript support for current component tests.

Each fixture supplies Shell.__init__, setting label, output, pid and fd, and
sets this module's OUT to its result directory.
"""
import gzip
import os
import select
import signal
import time

OUT = None
READY = b'\x1b]133;B\x1b\\'
CAPTURE = b'\x1eBUFFER:'
CONFIG = r'''
PROMPT='COMP> '
HISTFILE=$HOME/history
SAVEHIST=0
ZSHZ_DATA=$HOME/jump-data
[[ $COMP_CASE == vi ]] && bindkey -v
if [[ $COMP_CASE == eager-* || $COMP_CASE == existing ]]; then
  autoload -Uz compinit
  compinit -i -d "$HOME/.zcompdump"
fi
if [[ $COMP_CASE == custom-tab ]]; then
  _custom_tab() { BUFFER+='CUSTOMTAB'; CURSOR=$#BUFFER; }
  zle -N _custom_tab
  bindkey '^I' _custom_tab
fi
print -s 'print -r -- DEFER_AUTOSUGGEST_COMPLETE'
_state() {
  print -nr -- $'\x1eSTATE:'"$POSTDISPLAY|${#region_highlight}|${+functions[compdef]}|${_DEFERRED_RUNS:-0}|$WSH_AUTOSUGGESTIONS_OWNER|$WSH_SYNTAX_HIGHLIGHTING_OWNER|${_comps[z]:-}|$(bindkey '^I')"$'\x1f'
}
_custom() { BUFFER+='CUSTOM'; CURSOR=$#BUFFER; }
zle -N _state
zle -N _custom
bindkey '^T' _state
bindkey '^X' _custom
_capture() {
  print -nr -- $'\x1eBUFFER:'"$BUFFER"$'\x1f'
  BUFFER=''
  POSTDISPLAY=''
  CURSOR=0
  zle redisplay
}
zle -N _capture
bindkey '^G' _capture
'''

class Shell:
    def wait(self, marker, offset=0):
        deadline = time.monotonic() + 10
        while marker not in self.output[offset:]:
            if time.monotonic() >= deadline:
                raise RuntimeError('timeout: ' + self.label + repr(self.output[-2000:]))
            if select.select([self.fd], [], [], 0.1)[0]:
                self.output.extend(os.read(self.fd, 65536))

    def complete(self, text):
        return self.capture(text.encode() + b'\t')

    def capture(self, keys):
        offset = len(self.output)
        started = time.monotonic_ns()
        os.write(self.fd, keys + b'\x07')
        self.wait(b'\x1f', offset)
        elapsed = (time.monotonic_ns() - started) / 1e6
        start = self.output.index(CAPTURE, offset) + len(CAPTURE)
        end = self.output.index(b'\x1f', start)
        return self.output[start:end].decode(), elapsed

    def state(self):
        offset = len(self.output)
        os.write(self.fd, b'\x14')
        self.wait(b'\x1f', offset)
        start = self.output.index(b'\x1eSTATE:', offset) + len(b'\x1eSTATE:')
        end = self.output.index(b'\x1f', start)
        return self.output[start:end].decode().split('|')

    def close(self):
        os.kill(self.pid, signal.SIGHUP)
        os.waitpid(self.pid, 0)
        os.close(self.fd)
        with gzip.open(OUT / 'transcripts' / (self.label + '.gz'), 'wb') as stream:
            stream.write(self.output)
