#!/usr/bin/env zsh
builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
builtin cd -q -- "${0:A:h:h}"
python3 benchmarks/verify-historical.py
python3 benchmarks/verify-native-distribution.py
print -r -- 'PASS: complete retained-evidence suite'
