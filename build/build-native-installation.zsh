#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
readonly repository_root=${0:A:h:h}
export WSH_ZSH_SOURCE_LOCK=${repository_root}/build/zsh-sources/zsh-cad0d67c-native.json
python3 "${repository_root}/build/update-native-lock.py" --check
"${repository_root}/build/build-zsh.zsh"
export WSH_ZSH_ROOT=${WSH_ZSH_OUTPUT_ROOT:-${repository_root}/build/out}/$(jq -er .output_name "$WSH_ZSH_SOURCE_LOCK")
exec "${repository_root}/build/build-development-bundle.zsh" "$@"
