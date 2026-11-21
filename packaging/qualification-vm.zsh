#!/usr/bin/env zsh
# Create or start a disposable Fedora qualification VM for vm.py and test-login.py.
#   qualification-vm.zsh create RELEASE WORK   download and verify the Fedora Cloud image, write the seed
#   qualification-vm.zsh start WORK            boot it as the user unit wsh-fedora-compliance-vm
# The guest has the passwordless-sudo account `recovery`, reached by vm.py over SSH on
# 127.0.0.1:22284, and the test account `shellempty`, whose password `wsh-regression` the login
# and chsh tests type. Only one VM runs at a time, since vm.py always uses that port.
emulate -L zsh
setopt errexit nounset pipefail
readonly command=${1:?usage: qualification-vm.zsh create RELEASE WORK | start WORK}

if [[ $command == create ]]; then
  readonly release=${2:?release} work=${3:?work directory}
  [[ $release == <-> ]] || { print -u2 'error: RELEASE is a Fedora release number'; exit 1 }
  [[ ! -e $work ]] || { print -u2 "error: $work exists"; exit 1 }
  readonly key=/etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-$release-primary
  [[ -r $key ]] || { print -u2 "error: no Fedora $release signing key at $key; install fedora-gpg-keys"; exit 1 }
  readonly base=https://dl.fedoraproject.org/pub/fedora/linux/releases/$release/Cloud/x86_64/images
  mkdir -m 700 -p $work
  local listing=$(curl -fsSL $base/)
  local image=${${(M)${(f)listing}:#*Fedora-Cloud-Base-Generic-$release-*.x86_64.qcow2*}[1]}
  local checksum=${${(M)${(f)listing}:#*Fedora-Cloud-$release-*-x86_64-CHECKSUM*}[1]}
  image=${${image#*href=\"}%%\"*}; checksum=${${checksum#*href=\"}%%\"*}
  [[ -n $image && -n $checksum ]] || { print -u2 "error: no Generic cloud image under $base"; exit 1 }
  curl -fsSL -o $work/CHECKSUM $base/$checksum
  # The CHECKSUM file is signed with the release's primary key.
  local gnupg=$(mktemp -d)
  gpg --batch --quiet --homedir $gnupg --import $key
  gpg --batch --quiet --homedir $gnupg --verify $work/CHECKSUM 2>/dev/null || { print -u2 'error: CHECKSUM signature'; exit 1 }
  rm -rf -- "${gnupg:?}"
  curl -fsSL -o $work/base.qcow2 $base/$image
  local expected=${${(M)${(f)"$(<$work/CHECKSUM)"}:#SHA256 \($image\) = *}##* }
  [[ -n $expected && $(sha256sum $work/base.qcow2) == $expected\ * ]] || { print -u2 'error: image SHA-256'; exit 1 }
  print -r -- "$image $expected" > $work/base-image.txt
  chmod 400 $work/base.qcow2
  qemu-img create -q -f qcow2 -F qcow2 -b $work/base.qcow2 $work/guest.qcow2 16G
  # The client key logs in as recovery; the pinned host key lets vm.py run in batch mode.
  ssh-keygen -q -t ed25519 -N '' -C wsh-qualification -f $work/id_ed25519
  ssh-keygen -q -t ed25519 -N '' -C wsh-qualification-host -f $work/host_ed25519
  print -r -- "[127.0.0.1]:22284 $(cut -d' ' -f1,2 $work/host_ed25519.pub)" > $work/known_hosts
  local password=$(openssl passwd -6 wsh-regression)
  mkdir $work/seed
  print -r -- "instance-id: wsh-qualification-$release
local-hostname: wsh-qualification-$release" > $work/seed/meta-data
  {
    print -r -- '#cloud-config'
    print -r -- 'users:'
    print -r -- '  - name: recovery'
    print -r -- '    groups: [wheel]'
    print -r -- '    shell: /bin/bash'
    print -r -- '    sudo: ALL=(ALL) NOPASSWD:ALL'
    print -r -- '    ssh_authorized_keys:'
    print -r -- "      - $(<$work/id_ed25519.pub)"
    print -r -- '  - name: shellempty'
    print -r -- '    shell: /bin/bash'
    print -r -- '    lock_passwd: false'
    print -r -- "    passwd: $password"
    print -r -- 'ssh_pwauth: false'
    print -r -- 'disable_root: true'
    print -r -- 'ssh_deletekeys: true'
    print -r -- 'ssh_genkeytypes: [ed25519]'
    print -r -- 'ssh_keys:'
    print -r -- '  ed25519_private: |'
    sed 's/^/    /' $work/host_ed25519
    print -r -- "  ed25519_public: $(<$work/host_ed25519.pub)"
    print -r -- 'packages: [git-core, jq, python3]'
    print -r -- 'runcmd:'
    print -r -- '  - [systemctl, enable, --now, serial-getty@ttyS0.service]'
    print -r -- '  - [dnf, -y, copr, enable, wakamex/wsh]'
  } > $work/seed/user-data
  xorriso -as mkisofs -quiet -output $work/seed.iso -volid cidata -joliet -rock $work/seed/user-data $work/seed/meta-data
  print -r -- "Created Fedora $release qualification VM in $work from $image"
elif [[ $command == start ]]; then
  readonly work=${2:?work directory}
  systemctl --user reset-failed wsh-fedora-compliance-vm 2>/dev/null || :
  systemd-run --user --unit=wsh-fedora-compliance-vm --property=Restart=no \
    -p StandardOutput=file:$work/qemu.out -p StandardError=file:$work/qemu.err \
    /usr/bin/qemu-system-x86_64 -enable-kvm -cpu host -smp 4 -m 4096 \
    -drive file=$work/guest.qcow2,if=virtio,format=qcow2 -drive file=$work/seed.iso,media=cdrom,readonly=on \
    -netdev user,id=net0,hostfwd=tcp:127.0.0.1:22284-:22 -device virtio-net-pci,netdev=net0 -display none \
    -serial unix:$work/serial.sock,server=on,wait=off -monitor unix:$work/monitor.sock,server=on,wait=off
  local i
  for i in {1..60}; do
    if print true | WSH_VM_WORK=$work python3 ${0:A:h}/vm.py ping >/dev/null 2>&1; then
      # The first boot installs packages and enables the repository before it is ready.
      print 'cloud-init status --wait >/dev/null || :; cloud-init status --long' | WSH_VM_WORK=$work python3 ${0:A:h}/vm.py cloud-init
      print -r -- "VM up in $work"; exit 0
    fi
    sleep 5
  done
  print -u2 'error: the VM did not answer over SSH'; exit 1
else
  print -u2 "error: unknown command $command"; exit 1
fi
