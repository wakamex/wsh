#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
exec python3 ${0:A:h}/native-release.py collect "$@"
