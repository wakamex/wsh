#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

readonly root=${0:A:h:h}
builtin cd -q -- "$root"

# Shared local and CI entrypoint. Add accepted evidence checks here.
./tests/resource-gates.zsh
./benchmarks/verify-resource-gate-evidence.zsh
./benchmarks/verify-bootstrap-evidence.zsh
./benchmarks/verify-public-install-evidence.zsh
./benchmarks/verify-runtime-job-announcement-evidence.zsh
./benchmarks/verify-update-cli-evidence.zsh
./benchmarks/verify-bare-launch-evidence.zsh
./benchmarks/verify-config-coexistence-evidence.zsh
./benchmarks/verify-history-substring-search-evidence.zsh
./benchmarks/verify-autosuggestions-evidence.zsh
./benchmarks/verify-syntax-highlighting-evidence.zsh
./benchmarks/verify-edge-zsh-evidence.zsh
./benchmarks/verify-plugin-doctor-evidence.zsh
./benchmarks/verify-foreground-startup-evidence.zsh
./benchmarks/verify-native-terminal-integration-evidence.zsh
./benchmarks/verify-profile-evidence.zsh
./benchmarks/verify-profile-readiness-evidence.zsh
./benchmarks/verify-prompt-ownership-evidence.zsh
./benchmarks/verify-theme-selection-evidence.zsh
python3 ./benchmarks/verify-builtins-themes-evidence.py
python3 ./benchmarks/verify-profile-order-evidence.py
python3 ./benchmarks/verify-native-completion-evidence.py
python3 ./benchmarks/verify-deferred-completion-evidence.py
python3 ./benchmarks/verify-completion-cost-evidence.py

print -r -- 'PASS: complete retained-evidence suite'
