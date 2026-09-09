#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
readonly root=${0:A:h:h}
readonly source=${1:A}
readonly output=${2:A}
mkdir -p -- "$output"
${CC:-cc} -std=c11 -Wall -Wextra -Werror ${=CFLAGS:--O2} -fPIC -shared -I"$source/Src" -I"$source" \
    "$root/native/collector-module-prototype.c" "$root/native/git.c" ${=LDFLAGS:-} -pthread -lz -o "$output/wshcollector.so"
print -r -- "$output/wshcollector.so"
