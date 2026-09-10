#!/usr/bin/env zsh
builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
builtin cd -q -- "${0:A:h:h}"
python3 build/plugin-catalog.py --check
python3 tests/plugin-catalog-inputs.py
python3 benchmarks/verify-historical.py
python3 benchmarks/verify-native-distribution.py
python3 benchmarks/verify-native-retirement.py
python3 benchmarks/verify-complete-autosuggestions.py
python3 benchmarks/verify-highlighting-parser.py
python3 benchmarks/verify-installed-autosuggestions.py
python3 benchmarks/verify-highlight-none.py
python3 benchmarks/verify-highlight-traversal.py
python3 benchmarks/verify-highlight-full.py
python3 benchmarks/verify-installed-highlighting.py
python3 benchmarks/verify-highlighting-handoff.py
python3 benchmarks/verify-git-prompt-ownership.py
python3 benchmarks/verify-directory-takeover.py
python3 benchmarks/verify-older-autosuggestions.py
python3 benchmarks/verify-plugin-catalog.py
print -r -- 'PASS: complete retained-evidence suite'
