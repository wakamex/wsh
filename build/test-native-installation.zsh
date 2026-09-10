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
python3 $root/build/native_manifest.py verify $bundle
python3 $root/tests/native-manifest.py $bundle
python3 $root/native/check-installation.py $bundle $checks/contracts
python3 $root/native/test-installed-autosuggestions.py $bundle $checks/autosuggestions correctness
python3 $root/native/test-installed-autosuggestions.py $bundle $checks/autosuggestions-lifecycle lifecycle
python3 $root/native/test-installed-autosuggestions.py $bundle $checks/autosuggestions-bounds bounds
python3 $root/native/test-recovery.py $bundle $checks/recovery
python3 $root/native/test-profile.py $bundle $checks/profile
python3 $root/native/test-profile-report.py $bundle/bin/wsh $checks/profile-report --native
python3 $root/native/test-profile-storage.py $bundle/bin/wsh $checks/profile-storage
python3 $root/native/test-installed-completion.py $bundle $output/reference/zsh-cad0d67c-wsh2 $checks/completion correctness
python3 $root/native/test-history-owner.py $bundle/bin/wsh installed $checks/history correctness
python3 $root/native/prepare-directory-owner.py $checks/directory-fixture
python3 $root/native/test-directory-owner.py $bundle/bin/wsh installed $checks/directory-fixture $checks/directory
python3 $root/native/test-runtime-lifecycle.py $bundle/bin/wsh-runtime $checks/runtime-lifecycle
python3 $root/packaging/build-rpm.py $bundle $output/rpm
python3 $root/tests/native-release.py $output/rpm/RPMS/x86_64/*.rpm $bundle/manifest.json
print -r -- $checks > $output/checks-path
print -r -- $bundle > $output/installation-path
