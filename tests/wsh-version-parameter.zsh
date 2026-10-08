#!/usr/bin/env zsh
# WSH_VERSION identifies Wsh to every startup file and is not inherited by child processes.
emulate -L zsh
setopt errexit nounset pipefail
readonly binary=${1:?usage: wsh-version-parameter.zsh BINARY}
readonly home=$(mktemp -d /var/tmp/wsh-version-parameter.XXXXXX)
trap 'command rm -rf -- $home' EXIT
local version=${${(s: :)"$($binary --wsh-version)"}[2]}
[[ $version == <->.<->.<-> ]] || { print -u2 -- "FAIL: unexpected --wsh-version output: $version"; exit 1 }
print -r -- 'print -r -- "zshenv=${WSH_VERSION-unset}"' > $home/.zshenv
print -r -- 'print -r -- "zshrc=${WSH_VERSION-unset}"' > $home/.zshrc
local output=$(HOME=$home ZDOTDIR=$home WSH_VERSION=inherited timeout 10 $binary -ic \
  'print -r -- "child=${$(printenv WSH_VERSION)-}"' 2>&1)
local expected="zshenv=$version"$'\n'"zshrc=$version"$'\n'"child="
[[ $output == $expected ]] || { print -u2 -r -- "FAIL: expected ${(qqq)expected}, got ${(qqq)output}"; exit 1 }
print 'PASS: WSH_VERSION is set before startup files and not exported'
