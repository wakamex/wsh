#!/usr/bin/env zsh
builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
builtin cd -q -- "${0:A:h:h}"
python3 tests/public-release-login.py
python3 tests/native-build-status.py
python3 build/update-native-lock.py --check
python3 build/plugin-catalog.py --check
python3 tests/plugin-catalog-inputs.py
python3 tests/plugin-upstream-monitor.py
print -r -- 'PASS: current source contracts'
