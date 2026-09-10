#!/usr/bin/env python3
"""Install native main ownership while retaining the exact reference for recognition."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1])
source = (root / 'third_party/zsh-syntax-highlighting/highlighters/main/main-highlighter.zsh').read_text()
(out / 'known-main-highlighter.zsh').write_text(source)
adapter = source[:source.index('# Helper to deal with tokens crossing line boundaries.')]
adapter += '\n_zsh_highlight_highlighter_main_paint() { builtin wsh-highlight-main }\n'
adapter += 'typeset -ga ZSH_HIGHLIGHT_DIRS_BLACKLIST\n'
(out / 'main-highlighter.zsh').write_text(adapter)
