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
python3 ./benchmarks/verify-login-recovery-evidence.py
python3 ./benchmarks/verify-native-entrypoint-evidence.py

python3 ./benchmarks/verify-native-tools-evidence.py

python3 ./benchmarks/verify-native-doctor-evidence.py

python3 ./benchmarks/verify-native-foreground-evidence.py

python3 ./benchmarks/verify-native-build-evidence.py

python3 ./benchmarks/verify-native-package-evidence.py

python3 ./benchmarks/verify-native-profile-evidence.py

python3 ./benchmarks/verify-native-lifecycle-evidence.py

python3 ./benchmarks/verify-native-profile-isolation-evidence.py

python3 ./benchmarks/verify-git-pipe-lifetime-evidence.py
python3 ./benchmarks/verify-native-git-evidence.py
python3 ./benchmarks/verify-native-theme-parser-evidence.py

python3 ./benchmarks/verify-native-renderer-evidence.py

python3 ./benchmarks/verify-native-runtime-evidence.py

python3 ./benchmarks/verify-native-runtime-boundary-evidence.py

python3 ./benchmarks/verify-native-completion-scan-evidence.py

python3 ./benchmarks/verify-native-directory-query-evidence.py

python3 ./benchmarks/verify-native-history-kernel-evidence.py

python3 ./benchmarks/verify-native-suggestion-kernel-evidence.py

python3 ./benchmarks/verify-native-highlight-kernel-evidence.py

python3 ./benchmarks/verify-native-resource-paths-evidence.py

python3 ./benchmarks/verify-native-linked-modules-evidence.py

python3 ./benchmarks/verify-native-selected-runtime-evidence.py

python3 ./benchmarks/verify-native-final-package-evidence.py

python3 ./benchmarks/verify-native-migration-evidence.py

python3 ./benchmarks/verify-native-floor-evidence.py

python3 ./benchmarks/verify-native-inventory-evidence.py

python3 ./benchmarks/verify-native-components-evidence.py

python3 ./benchmarks/verify-native-completion-adoption.py

python3 ./benchmarks/verify-native-history-adoption.py

python3 ./benchmarks/verify-native-directory-adoption.py

python3 ./benchmarks/verify-native-directory-confirmation.py

python3 ./benchmarks/verify-native-directory-mount.py

python3 ./benchmarks/verify-native-directory-installed.py

python3 ./benchmarks/verify-native-directory-floor.py

python3 ./benchmarks/verify-native-build-migration.py

print -r -- 'PASS: complete retained-evidence suite'
