# Version and release are fixed when preparing the source RPM.
%{!?wsh_version:%global wsh_version 0.4.0}
%{!?wsh_release:%global wsh_release 1}

# Keep distro post-processing, then inventory the bytes it will package even
# when rpmbuild is invoked with --nocheck.
%global __os_install_post %{__os_install_post} \
    python3 packaging/source-build.py finalize %{buildroot}%{_prefix}

Name:           wsh
Version:        %{wsh_version}
Release:        %{wsh_release}%{?dist}
Summary:        Interactive shell with diagnostics and profiling
License:        MIT AND MIT-Modern-Variant AND ISC AND GPL-2.0-only AND BSD-3-Clause
URL:            https://github.com/wakamex/wsh
Source0:        https://github.com/wakamex/wsh/archive/%{wsh_commit}.tar.gz#/wsh-%{wsh_commit}.tar.gz
Source1:        https://github.com/zsh-users/zsh/archive/cad0d67c76e2be7371cf3526b79ea2581810d35a/zsh-cad0d67c76e2be7371cf3526b79ea2581810d35a.tar.gz
# Generated identity and hashes, kept separate from unmodified upstream bytes:
# python3 packaging/build-source-rpm.py OUTPUT --status release
Source2:        wsh-source-info.json
# Wsh maintains a patched tomlc17 with unsigned integer and correctness fixes.
# It has no system-library build mode; see packaging/FEDORA-REVIEW.md.
Provides:       bundled(tomlc17) = 0^20260822git64a063b
# The native owners retain generated adapters and selected plugin lifecycle code.
Provides:       bundled(zsh-autosuggestions) = 0.7.1
Provides:       bundled(zsh-history-substring-search) = 1.1.0^20260115git14c8d2e
Provides:       bundled(zsh-syntax-highlighting) = 0.8.1~20260822git2fc57d6
Provides:       bundled(zsh-z) = 2.0^20260901git9112b53

BuildRequires:  redhat-rpm-config
BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  autoconf
BuildRequires:  python3 >= 3.9
BuildRequires:  zsh
BuildRequires:  git-core
BuildRequires:  jq
BuildRequires:  curl
BuildRequires:  binutils
BuildRequires:  patch
BuildRequires:  tar
BuildRequires:  gzip
BuildRequires:  coreutils
BuildRequires:  findutils
BuildRequires:  diffutils
BuildRequires:  gawk
BuildRequires:  grep
BuildRequires:  sed
BuildRequires:  ncurses-devel
BuildRequires:  libcap-devel
BuildRequires:  pcre2-devel
BuildRequires:  jansson-devel
BuildRequires:  zlib-devel
BuildRequires:  hardlink
Requires:       git-core
Requires(post): /usr/bin/grep
Requires(postun): /usr/bin/sed

%description
Wsh provides Zsh-compatible interactive defaults, diagnostics and profiling.
System packages own installation and updates.

%prep
%setup -q -n wsh-%{wsh_commit}
cp -p %{SOURCE2} source-info.json
mkdir -p build/cache
cp -p %{SOURCE1} build/cache/
python3 packaging/source-build.py verify
# Preserve the upstream shell's license alongside the Wsh license.
mkdir package-licenses
cp -p LICENSE package-licenses/WSH-MIT
tar -xOf %{SOURCE1} --wildcards '*/LICENCE' > package-licenses/ZSH
cp -p third_party/tomlc17/LICENSE package-licenses/TOMLC17-MIT
cp -p third_party/zsh-autosuggestions/LICENSE package-licenses/AUTOSUGGESTIONS-MIT
cp -p third_party/zsh-syntax-highlighting/COPYING.md package-licenses/HIGHLIGHTING-BSD
cp -p third_party/zsh-z/LICENSE package-licenses/ZSH-Z-MIT
cp -p third_party/oh-my-zsh-git-prompt/LICENSE.txt package-licenses/OMZ-MIT
cp -p packaging/licenses/GPL-2.0-only.txt package-licenses/GPL-2.0-only
tar -xOf %{SOURCE1} --wildcards '*/Src/openssh_bsd_setres_id.c' | sed -n '1,/^ \*\//p' > package-licenses/OPENSSH-ISC

%build
export CFLAGS="%{optflags}"
export LDFLAGS="%{?build_ldflags}"
export WSH_BUILD_JOBS="%{_smp_build_ncpus}"
python3 packaging/source-build.py build

%install
python3 packaging/source-build.py install %{buildroot}%{_prefix}
install -D -p -m 0644 packaging/wsh.1 %{buildroot}%{_mandir}/man1/wsh.1
# Keep exact comparison inputs without storing duplicate payload bytes.
hardlink -c %{buildroot}%{_datadir}/wsh

%check
python3 packaging/source-build.py check %{buildroot}%{_prefix}

%post
: >> /etc/shells
for shell in /usr/bin/wsh /bin/wsh; do
    grep -qxF "$shell" /etc/shells || echo "$shell" >> /etc/shells
done
exit 0

%postun
if [ "$1" = 0 ] && [ -f /etc/shells ]; then
    sed -i '\!^/usr/bin/wsh$!d; \!^/bin/wsh$!d' /etc/shells
fi
exit 0

%files
%license package-licenses/*
%doc README.md NATIVE-INSTALLATION.md
%{_bindir}/wsh
%{_libexecdir}/wsh
%{_datadir}/wsh
%{_mandir}/man1/wsh.1*

%changelog
* Sun Sep 13 2026 Mihai Cosma <wakamex@users.noreply.github.com> - 0.4.0-1
- Use the Fedora filesystem layout, license tagging and shell scriptlets.
- Declare bundled parser provenance and preserve offline source-build tests.
