#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
readonly root=${0:A:h:h}
readonly bundle=${1:A}
readonly reference=${2:A}
readonly checks=${3:A}
mkdir -p $checks
export WSH_REFERENCE_ZSH=$reference/bin/zsh WSH_TEST_ZSH=$reference/bin/zsh
python3 $root/build/native_manifest.py verify $bundle
python3 $root/tests/native-build-status.py $bundle
python3 $root/tests/native-manifest.py $bundle
python3 $root/native/test-highlight-roundtrip.py $bundle/bin/wsh $checks/highlight-roundtrip
python3 $root/native/test-installed-highlighting.py $bundle $checks/highlighting
python3 $root/native/check-installation.py $bundle $checks/contracts
python3 $root/native/test-installed-autosuggestions.py $bundle $checks/autosuggestions correctness
python3 $root/native/test-installed-autosuggestions.py $bundle $checks/autosuggestions-lifecycle lifecycle
python3 $root/native/test-installed-autosuggestions.py $bundle $checks/autosuggestions-bounds bounds
python3 $root/native/test-recovery.py $bundle $checks/recovery
python3 $root/native/test-profile.py $bundle $checks/profile
python3 $root/native/test-profile-report.py $bundle/bin/wsh $checks/profile-report --native
python3 $root/native/test-profile-storage.py $bundle/bin/wsh $checks/profile-storage
python3 $root/native/test-installed-completion.py $bundle $reference $checks/completion correctness
python3 $root/native/test-history-owner.py $bundle/bin/wsh installed $checks/history correctness
python3 $root/native/prepare-directory-owner.py $checks/directory-fixture
python3 $root/native/test-directory-owner.py $bundle/bin/wsh installed $checks/directory-fixture $checks/directory
python3 $root/native/test-runtime-lifecycle.py $bundle/bin/wsh-runtime $checks/runtime-lifecycle
