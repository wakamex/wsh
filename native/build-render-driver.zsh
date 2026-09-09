#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
readonly root=${0:A:h:h}
readonly output=${1:A}
"$root/native/build-theme-prototype.zsh" "$output"
(cd "$root/third_party/yyjson" && sha256sum -c SHA256SUMS)
${CC:-cc} -std=c17 -Wall -Wextra -Werror ${=CFLAGS:--O2} -I"$output" -I"$root/third_party/yyjson" \
    "$root/native/theme.c" "$root/native/render.c" "$root/native/render-driver.c" \
    "$output/tomlc17.c" "$root/third_party/yyjson/yyjson.c" ${=LDFLAGS:-} -o "$output/render-driver"
print -r -- "$output/render-driver"
