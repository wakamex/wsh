#!/usr/bin/env zsh
builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail
(( $# == 2 )) || exit 2
readonly manager=${1:A} bundle=${2:A}
readonly scratch=$(mktemp -d /var/tmp/wsh-named-themes.XXXXXX)
trap 'rm -rf -- $scratch' EXIT INT TERM
mkdir -p $scratch/home
$manager bundle activate $bundle --state-root $scratch/state >/dev/null
for theme in minimal wakamex robbyrussell agnoster; do
  $bundle/bin/wsh-runtime validate-theme $bundle/share/wsh/themes/$theme.toml >/dev/null
  HOME=$scratch/home ZDOTDIR=$scratch/home WSH_THEME=$theme EXPECT_THEME=$theme \
    $manager run --state-root $scratch/state -- -dic '[[ $WSH_THEME == $EXPECT_THEME && $WSH_PROMPT_OWNER == wsh && $WSH_RUNTIME_READY == 1 ]]'
  print -r -- "PASS: $theme resolves through the launcher and validated runtime"
done
