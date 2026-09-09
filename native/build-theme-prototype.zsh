#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
readonly root=${0:A:h:h}
readonly output=${1:A}
mkdir -p -- "$output"
(cd "$root/third_party/tomlc17" && sha256sum -c SHA256SUMS)
cp "$root/third_party/tomlc17/"tomlc17.{c,h} "$output/"
patch -d "$output" -p1 < "$root/native/tomlc17-wsh.patch"
${CC:-cc} -std=c17 -Wall -Wextra -Werror ${=CFLAGS:--O2} -I"$output" \
    "$root/native/theme.c" "$root/native/theme-prototype.c" "$output/tomlc17.c" \
    ${=LDFLAGS:-} -o "$output/wsh-theme-prototype"
print -r -- "$output/wsh-theme-prototype"
