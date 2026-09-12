#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
readonly root=${0:A:h:h}
readonly output=${1:?usage: test-source-rpm.zsh NEW_OUTPUT}
[[ ! -e $output ]] || { print -u2 'error: use a new output directory'; exit 1; }
mkdir -p $output
readonly destination=${output:A}
python3 $root/packaging/build-source-rpm.py $destination/source > $destination/source.log 2>&1
packages=($destination/source/SRPMS/*.src.rpm(N))
(( $#packages == 1 ))
mkdir $destination/context $destination/rebuild
cp $packages[1] $destination/context/wsh.src.rpm
cp $root/packaging/Containerfile.source-rpm $destination/context/Containerfile
identity=$(sha256sum $packages[1])
readonly image=localhost/wsh-source-rpm:${identity[1,16]}
podman build --tag $image $destination/context > $destination/builder.log 2>&1
podman image inspect $image > $destination/builder.json
# The builder sees the SRPM and test driver, not the repository or host caches.
podman run --rm --init --userns=keep-id --network=none \
  --volume $destination/source/SRPMS:/sources:ro,Z \
  --volume $destination/rebuild:/builddir:Z \
  --volume $root/tests/source-rpm.py:/test-source-rpm.py:ro,z \
  $image bash -ec '
    rpm -qa | LC_ALL=C sort > /builddir/packages.txt
    python3 /test-source-rpm.py /sources/*.src.rpm
    rpmbuild --rebuild /sources/*.src.rpm --define "_topdir /builddir" --define "_smp_build_ncpus 4"
  ' > $destination/rebuild.log 2>&1
print -r -- "PASS: source RPM integrity, offline Fedora rebuild and native checks: $destination"
