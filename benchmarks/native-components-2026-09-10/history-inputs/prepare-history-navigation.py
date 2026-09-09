#!/usr/bin/env python3
"""Retain ZLE/highlight adapters around a private C navigation owner."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]).resolve()
out.mkdir(parents=True, exist_ok=True)
s = (root/'third_party/zsh-history-substring-search/zsh-history-substring-search.zsh').read_text()
(out/'control.zsh').write_text(s)
a = s.index('_history-substring-search-begin() {')
b = s.index('_history-substring-search-end() {', a)
s = s[:a] + '_history-substring-search-begin() { setopt localoptions extendedglob; wsh-history-begin }\n\n' + s[b:]
a = s.index('_history_substring_search_process_raw_matches() {')
s = s[:a] + '''_history-substring-search-up-search() { wsh-history-navigate up }
_history-substring-search-down-search() { wsh-history-navigate down }
'''
(out/'candidate.zsh').write_text(s)
