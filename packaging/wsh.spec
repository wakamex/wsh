# Version and release are fixed when preparing the source RPM.
%{!?wsh_version:%global wsh_version 0.3.1}
%{!?wsh_release:%global wsh_release 0.1}

# Keep distro post-processing, then inventory the bytes it will package even
# when rpmbuild is invoked with --nocheck.
%global __os_install_post %{__os_install_post} \
    python3 packaging/source-build.py finalize %{buildroot}%{_libexecdir}/wsh

Name:           wsh
Version:        %{wsh_version}
Release:        %{wsh_release}%{?dist}
Summary:        Zsh distribution with native diagnostics and interactive defaults
License:        MIT AND Zsh AND BSD-3-Clause
URL:            https://github.com/wakamex/wsh
Source0:        wsh-%{version}.tar.gz
Source1:        zsh-cad0d67c76e2be7371cf3526b79ea2581810d35a.tar.gz
ExclusiveArch:  x86_64

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
Requires:       git-core
Requires(post): /usr/bin/grep
Requires(preun): /usr/bin/awk
Requires(postun): /usr/bin/sed

%description
Wsh provides Zsh-compatible interactive defaults, diagnostics and profiling.
System packages own installation and updates.

%prep
%setup -q
mkdir -p build/cache
cp -p %{SOURCE1} build/cache/
python3 packaging/source-build.py verify
# Preserve the upstream shell's license alongside the Wsh license.
tar -xOf %{SOURCE1} --wildcards '*/LICENCE' > ZSH-LICENSE

%build
export CFLAGS="%{optflags}"
export LDFLAGS="%{?build_ldflags}"
export WSH_BUILD_JOBS="%{_smp_build_ncpus}"
python3 packaging/source-build.py build

%install
python3 packaging/source-build.py install %{buildroot}%{_libexecdir}/wsh
mkdir -p %{buildroot}%{_bindir}
ln -s ../libexec/wsh/bin/wsh %{buildroot}%{_bindir}/wsh

%check
python3 packaging/source-build.py check %{buildroot}%{_libexecdir}/wsh

%post
touch /etc/shells
for shell in /usr/bin/wsh /bin/wsh; do
    grep -qxF "$shell" /etc/shells || echo "$shell" >> /etc/shells
done
exit 0

%preun
if [ "$1" = 0 ] && awk -F: '$7 == "/usr/bin/wsh" || $7 == "/bin/wsh" { found = 1 } END { exit !found }' /etc/passwd; then
    echo 'Wsh is still a local account shell. Change those accounts to another installed shell before removal.' >&2
    exit 1
fi
exit 0

%postun
if [ "$1" = 0 ] && [ -f /etc/shells ]; then
    sed -i '\!^/usr/bin/wsh$!d; \!^/bin/wsh$!d' /etc/shells
fi
exit 0

%files
%license LICENSE ZSH-LICENSE
%doc README.md NATIVE-INSTALLATION.md
%{_bindir}/wsh
%{_libexecdir}/wsh
