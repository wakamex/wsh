#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
readonly root=${0:A:h:h:h}
readonly experiment=${0:A:h}
readonly installation=${1:A}
readonly work=${2:A}
[[ ! -e $work ]] || { print -u2 -- 'Use a new output directory'; exit 2; }
mkdir -p $work/candidate $work/tmp
export TMPDIR=$work/tmp TMPPREFIX=$work/tmp/zsh
unset FPATH
export CFLAGS=${CFLAGS:--O2}
cd $root
cp native/{runtime.c,runtime-json.h,runtime-trace.c,runtime-trace.h} $work/candidate/
patch -d $work/candidate -p2 < $experiment/candidate.patch
zsh -df native/build-runtime.zsh $work/control > $work/build-control.log 2>&1
${CC:-cc} -std=c17 -Wall -Wextra -Werror ${=CFLAGS} ${=CPPFLAGS:-} \
  "-ffile-prefix-map=$root=." "-ffile-prefix-map=$work=./native-build" \
  -I$work/control -Inative native/theme.c native/render.c native/git.c \
  $work/candidate/runtime.c $work/candidate/runtime-trace.c $work/control/tomlc17.c \
  ${=LDFLAGS:-} -ljansson -pthread -lz -o $work/candidate/wsh-runtime
${WSH_SANITIZER_CC:-clang} -std=c17 -Wall -Wextra -Werror ${=CFLAGS} ${=CPPFLAGS:-} \
  -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer \
  -I$work/control -Inative native/theme.c native/render.c native/git.c \
  $work/candidate/runtime.c $work/candidate/runtime-trace.c $work/control/tomlc17.c \
  ${=LDFLAGS:-} -ljansson -pthread -lz -o $work/candidate/wsh-runtime-sanitized
python3 $experiment/protocol.py $work/control/wsh-runtime $work/candidate/wsh-runtime $work/protocol
python3 native/test-runtime-lifecycle.py $work/control/wsh-runtime $work/lifecycle-control
python3 native/test-runtime-lifecycle.py $work/candidate/wsh-runtime $work/lifecycle-candidate
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 \
  python3 native/test-runtime-lifecycle.py $work/candidate/wsh-runtime-sanitized $work/lifecycle-sanitized
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 \
  python3 $experiment/protocol.py $work/control/wsh-runtime $work/candidate/wsh-runtime-sanitized $work/protocol-sanitized
for variant in control candidate; do
  cp -a --reflink=auto $installation $work/$variant-installation
  cp $work/$variant/wsh-runtime $work/$variant-installation/bin/wsh-runtime
  python3 build/native_manifest.py create $work/$variant-installation build/zsh-sources/zsh-cad0d67c-native.json
done
python3 native/test-profile.py $work/candidate-installation $work/profile
zsh -df tests/named-themes.zsh $work/candidate-installation
python3 native/measure-git.py $work/control/wsh-runtime $work/candidate/wsh-runtime $work/git
python3 native/measure-startup.py $work/control-installation $work/candidate-installation $work/startup
python3 native/measure-linked-memory.py $work/control-installation $work/candidate-installation $work/memory
python3 $experiment/ping.py $work/control/wsh-runtime $work/candidate/wsh-runtime $work/ping.json
