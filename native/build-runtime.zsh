#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
readonly root=${0:A:h:h}
readonly output=${1:A}
"$root/native/build-theme-prototype.zsh" "$output"
${CC:-gcc} -std=c17 -Wall -Wextra -Werror ${=CFLAGS:--O2} ${=CPPFLAGS:-} \
    "-ffile-prefix-map=$root=." "-ffile-prefix-map=$output=./native-build" \
    -I"$output" \
    "$root/native/theme.c" "$root/native/render.c" "$root/native/git.c" "$root/native/runtime.c" "$root/native/runtime-trace.c" \
    "$output/tomlc17.c" ${=LDFLAGS:-} -ljansson -pthread -lz -o "$output/wsh-runtime"
print -r -- "$output/wsh-runtime"
