#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
readonly root=${0:A:h:h}
readonly output=${WSH_NATIVE_OUTPUT_ROOT:-$root/build/portable/glibc-2.28}
mkdir -p $output
# Use the same pinned upstream shell with terminal patches as the reference.
WSH_ZSH_SOURCE_LOCK=$root/build/zsh-sources/zsh-cad0d67c.json \
WSH_ZSH_OUTPUT_ROOT=$output/reference $root/build/build-zsh.zsh
export WSH_REFERENCE_ZSH=$output/reference/zsh-cad0d67c-wsh2/bin/zsh
export WSH_TEST_ZSH=$WSH_REFERENCE_ZSH
export WSH_ZSH_OUTPUT_ROOT=$output/zsh WSH_BUNDLE_OUTPUT_ROOT=$output/bundles
$root/build/build-native-installation.zsh > $output/build.log 2>&1
readonly bundle=$(tail -n 1 $output/build.log)
readonly checks=$(mktemp -d $output/checks.XXXXXX)
$root/build/check-native-installation.zsh $bundle $output/reference/zsh-cad0d67c-wsh2 $checks
python3 $root/packaging/build-rpm.py $bundle $output/rpm
python3 $root/tests/native-release.py $output/rpm/RPMS/x86_64/*.rpm $bundle/manifest.json
print -r -- $checks > $output/checks-path
print -r -- $bundle > $output/installation-path
