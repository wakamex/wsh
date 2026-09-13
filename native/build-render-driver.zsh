#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
readonly root=${0:A:h:h}
readonly output=${1:A}
"$root/native/build-theme-prototype.zsh" "$output"
${CC:-cc} -std=c17 -Wall -Wextra -Werror ${=CFLAGS:--O2} ${=CPPFLAGS:-} -I"$output" \
    "$root/native/theme.c" "$root/native/render.c" "$root/native/render-driver.c" \
    "$output/tomlc17.c" ${=LDFLAGS:-} -ljansson -o "$output/render-driver"
print -r -- "$output/render-driver"
