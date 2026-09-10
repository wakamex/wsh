%global debug_package %{nil}
%global __os_install_post %{nil}
%{!?wsh_release:%global wsh_release 0.1}
%{!?wsh_fault:%global wsh_fault none}

Name:           wsh
Version:        %{wsh_version}
Release:        %{wsh_release}%{?dist}
Summary:        Zsh distribution with native diagnostics and interactive defaults
License:        MIT AND Zsh AND BSD-3-Clause
URL:            https://github.com/wakamex/wsh
Source0:        native-payload.tar.gz
Requires:       /bin/sh
Requires(preun): /usr/bin/awk
Requires(post): /usr/bin/grep
Requires(postun): /usr/bin/sed

%description
Wsh provides Zsh-compatible interactive defaults, diagnostics and profiling.
System packages own installation and updates.

%prep
%setup -q -c -T
tar -xzf %{SOURCE0}

%build
# The payload has already passed its separately retained native build tests.

%install
mkdir -p %{buildroot}%{_libexecdir}/wsh %{buildroot}%{_bindir}
cp -a payload/. %{buildroot}%{_libexecdir}/wsh/
# Normalize the entire private per-user payload for a root-owned installation.
find %{buildroot}%{_libexecdir}/wsh -type d -exec chmod 0755 {} +
find %{buildroot}%{_libexecdir}/wsh -type f -exec chmod 0644 {} +
chmod 0755 %{buildroot}%{_libexecdir}/wsh/bin/*
ln -s ../libexec/wsh/bin/wsh %{buildroot}%{_bindir}/wsh

%pre
if [ '%{wsh_fault}' = pre ]; then
    echo 'injected pre-install failure' >&2
    exit 1
fi

%post
touch /etc/shells
for shell in /usr/bin/wsh /bin/wsh; do
    grep -qxF "$shell" /etc/shells || echo "$shell" >> /etc/shells
done
if [ '%{wsh_fault}' = post ]; then
    echo 'injected post-install failure' >&2
    exit 1
fi
if [ '%{wsh_fault}' = pause ]; then
    touch /run/wsh-rpm-post-paused
    sleep 120
fi
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
%{_bindir}/wsh
%{_libexecdir}/wsh
