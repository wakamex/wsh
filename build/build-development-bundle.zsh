#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly zsh_source_lock=${WSH_ZSH_SOURCE_LOCK:-${script_dir}/zsh-sources/zsh-cad0d67c-native.json}
readonly zsh_output_root=${WSH_ZSH_OUTPUT_ROOT:-${repository_root}/build/out}
readonly output_root=${WSH_BUNDLE_OUTPUT_ROOT:-${repository_root}/bundles}
readonly bundle_status=${WSH_BUNDLE_STATUS:-development}

for command in cp find git head install jq ld mktemp mv python3 readelf rm sed sha256sum sort stat; do
  if (( ! $+commands[$command] )); then
    print -u2 -- "error: required command not found: ${command}"
    exit 1
  fi
done

readonly zsh_version=$(jq -er '.version' "$zsh_source_lock")
readonly zsh_output_name=$(jq -er '.output_name' "$zsh_source_lock")
zsh_source_lock_sha256=$(sha256sum "$zsh_source_lock")
readonly zsh_source_lock_sha256=${zsh_source_lock_sha256%% *}
if [[ -n ${WSH_ZSH_ROOT:-} ]]; then
  readonly zsh_root=$WSH_ZSH_ROOT
else
  WSH_ZSH_SOURCE_LOCK=$zsh_source_lock \
    WSH_ZSH_OUTPUT_ROOT=$zsh_output_root \
    "${script_dir}/build-zsh.zsh" >/dev/null
  readonly zsh_root=${zsh_output_root}/${zsh_output_name}
fi
[[ ${zsh_root:t} == $zsh_output_name ]] || {
  print -u2 -- "error: Zsh root does not match source lock output: ${zsh_root}"
  exit 1
}
[[ -r ${zsh_root}/.wsh-source-lock.sha256 && $(<${zsh_root}/.wsh-source-lock.sha256) == $zsh_source_lock_sha256 ]] || {
  print -u2 -- "error: Zsh root was not built from the selected source lock: ${zsh_root}"
  exit 1
}
if jq -e 'has("native")' "$zsh_source_lock" >/dev/null; then
  native_build_identity=$(python3 "${repository_root}/native/prepare-build.py" "$zsh_source_lock")
  [[ -r ${zsh_root}/.wsh-native-build.sha256 && $(<${zsh_root}/.wsh-native-build.sha256) == $native_build_identity ]] || {
    print -u2 -- 'error: native source or compiler identity differs from the selected Zsh build'
    exit 1
  }
fi
cd "$repository_root"
if jq -e 'has("native")' "$zsh_source_lock" >/dev/null; then
  : # Native assembly uses the shared inventory verifier.
else
  print -u2 -- "error: use a native source lock for installation assembly"
  exit 1
fi

mkdir -p -- "$output_root"
stage=$(mktemp -d "${output_root}/.development.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT INT TERM
chmod 700 "$stage"

install -D -m 755 "${zsh_root}/bin/zsh" "${stage}/bin/zsh"
if jq -e 'has("native")' "$zsh_source_lock" >/dev/null; then
  install -D -m 755 "${zsh_root}/bin/wsh" "${stage}/bin/wsh"
fi
if jq -e 'has("native")' "$zsh_source_lock" >/dev/null; then
  "${repository_root}/native/build-runtime.zsh" "$stage/.runtime-build"
  install -D -m 755 "$stage/.runtime-build/wsh-runtime" "${stage}/bin/wsh-runtime"
  rm -rf -- "$stage/.runtime-build"
  install -D -m 644 "$zsh_source_lock" "$stage/share/wsh/native-source-lock.json"
  install -D -m 644 "$zsh_root/.wsh-config.modules" "$stage/share/wsh/config.modules"
  install -D -m 644 "$repository_root/third_party/tomlc17/LICENSE" "$stage/share/wsh/licenses/tomlc17-LICENSE"
  install -D -m 644 "$repository_root/third_party/yyjson/LICENSE" "$stage/share/wsh/licenses/yyjson-LICENSE"

fi
if [[ -d ${zsh_root}/lib ]]; then
  cp -R -- "${zsh_root}/lib" "$stage/lib"
elif jq -e '.native.linked_modules == true' "$zsh_source_lock" >/dev/null; then
  mkdir -p -- "$stage/lib/zsh/${zsh_version}"
else
  print -u2 -- 'error: dynamic Zsh build is missing its module directory'
  exit 1
fi
mkdir -p -- "${stage}/share/zsh/${zsh_version}"
cp -R -- "${zsh_root}/share/zsh/${zsh_version}/functions" "${stage}/share/zsh/${zsh_version}/functions"
install -D -m 644 "${repository_root}/integration/integration.zsh" "${stage}/share/wsh/integration.zsh"
install -D -m 644 "${repository_root}/integration/profile.zsh" "${stage}/share/wsh/profile.zsh"
install -D -m 644 "${repository_root}/integration/history-substring-search.zsh" "${stage}/share/wsh/defaults/history-substring-search.zsh"
install -D -m 644 "${repository_root}/third_party/zsh-history-substring-search/zsh-history-substring-search.zsh" "${stage}/share/wsh/defaults/zsh-history-substring-search.zsh"
install -D -m 644 "${repository_root}/third_party/zsh-history-substring-search/oh-my-zsh-history-substring-search.zsh" "${stage}/share/wsh/defaults/known-oh-my-zsh-history-substring-search.zsh"
install -D -m 644 "${repository_root}/third_party/zsh-history-substring-search/PROVENANCE.md" "${stage}/share/wsh/defaults/zsh-history-substring-search-PROVENANCE.md"
install -D -m 644 "${repository_root}/third_party/zsh-history-substring-search/OH-MY-ZSH-LICENSE.txt" "${stage}/share/wsh/defaults/zsh-history-substring-search-OH-MY-ZSH-LICENSE.txt"
(cd "${stage}/share/wsh/defaults" && "${stage}/bin/zsh" -fc 'zcompile zsh-history-substring-search.zsh.zwc zsh-history-substring-search.zsh')
chmod 644 "${stage}/share/wsh/defaults/zsh-history-substring-search.zsh.zwc"
install -D -m 644 "${repository_root}/integration/autosuggestions.zsh" "${stage}/share/wsh/defaults/autosuggestions.zsh"
install -D -m 644 "${repository_root}/third_party/zsh-autosuggestions/zsh-autosuggestions.zsh" "${stage}/share/wsh/defaults/zsh-autosuggestions.zsh"
install -D -m 644 "${repository_root}/third_party/zsh-autosuggestions/known-0.7.0.zsh" "${stage}/share/wsh/defaults/known-zsh-autosuggestions-0.7.0.zsh"
install -D -m 644 "${repository_root}/third_party/zsh-autosuggestions/PROVENANCE.md" "${stage}/share/wsh/defaults/zsh-autosuggestions-PROVENANCE.md"
install -D -m 644 "${repository_root}/third_party/zsh-autosuggestions/LICENSE" "${stage}/share/wsh/defaults/zsh-autosuggestions-LICENSE"
(cd "${stage}/share/wsh/defaults" && "${stage}/bin/zsh" -fc 'zcompile zsh-autosuggestions.zsh.zwc zsh-autosuggestions.zsh')
chmod 644 "${stage}/share/wsh/defaults/zsh-autosuggestions.zsh.zwc"
install -D -m 644 "${repository_root}/integration/git-prompt.zsh" "${stage}/share/wsh/defaults/git-prompt.zsh"
cp -R -- "${repository_root}/third_party/oh-my-zsh-git-prompt" "${stage}/share/wsh/defaults/oh-my-zsh-git-prompt"
install -D -m 644 "${repository_root}/integration/syntax-highlighting.zsh" "${stage}/share/wsh/defaults/syntax-highlighting.zsh"
cp -R -- "${repository_root}/third_party/zsh-syntax-highlighting" "${stage}/share/wsh/defaults/zsh-syntax-highlighting"
if jq -e 'has("native")' "$zsh_source_lock" >/dev/null; then
  python3 "${repository_root}/native/prepare-highlighting.py" "${stage}/share/wsh/defaults/zsh-syntax-highlighting/highlighters/main"
fi
(cd "${stage}/share/wsh/defaults/zsh-syntax-highlighting" && "${stage}/bin/zsh" -fc 'zcompile zsh-syntax-highlighting.zsh.zwc zsh-syntax-highlighting.zsh; for source in highlighters/*/*-highlighter.zsh; do zcompile ${source}.zwc $source; done')
find "${stage}/share/wsh/defaults/zsh-syntax-highlighting" -type f -exec chmod 644 {} +
if jq -e 'has("native")' "$zsh_source_lock" >/dev/null; then
  python3 "${repository_root}/native/prepare-autosuggestions.py" "${stage}/.autosuggestion-fixture"
  install -D -m 644 "${stage}/.autosuggestion-fixture/candidate.zsh" "${stage}/share/wsh/defaults/native-autosuggestions.zsh"
  rm -rf "${stage}/.autosuggestion-fixture"
  (cd "${stage}/share/wsh/defaults" && "${stage}/bin/zsh" -fc 'zcompile native-autosuggestions.zsh.zwc native-autosuggestions.zsh')
  chmod 644 "${stage}/share/wsh/defaults/native-autosuggestions.zsh.zwc"
  install -D -m 644 "${repository_root}/integration/native-history.zsh" "${stage}/share/wsh/defaults/native-history.zsh"
  install -D -m 644 "${repository_root}/integration/native-before.zsh" "${stage}/share/wsh/native-before.zsh"
  install -D -m 644 "${repository_root}/integration/native-after.zsh" "${stage}/share/wsh/native-after.zsh"

fi
install -D -m 644 "${repository_root}/schemas/theme.schema.json" "${stage}/share/wsh/schemas/theme.schema.json"
install -D -m 644 "${repository_root}/integration/directory-jump.zsh" "${stage}/share/wsh/defaults/directory-jump.zsh"
cp -R -- "${repository_root}/third_party/zsh-z" "${stage}/share/wsh/defaults/zsh-z"
if jq -e 'has("native")' "$zsh_source_lock" >/dev/null; then
  python3 "${repository_root}/native/prepare-directory-owner.py" "${stage}/.directory-fixture"
  install -D -m 644 "${stage}/.directory-fixture/candidate.zsh" "${stage}/share/wsh/defaults/zsh-z/native.zsh"
  install -D -m 644 "${stage}/.directory-fixture/takeover.zsh" "${stage}/share/wsh/defaults/zsh-z/takeover.zsh"
  rm -rf "${stage}/.directory-fixture"
  (cd "${stage}/share/wsh/defaults/zsh-z" && "${stage}/bin/zsh" -fc 'zcompile native.zsh.zwc native.zsh')
fi
mv "${stage}/share/wsh/defaults/zsh-z/_z" "${stage}/share/wsh/defaults/zsh-z/_zshz"
(cd "${stage}/share/wsh/defaults/zsh-z" && "${stage}/bin/zsh" -fc 'zcompile z.plugin.zsh.zwc z.plugin.zsh')
find "${stage}/share/wsh/defaults/zsh-z" -type f -exec chmod 644 {} +
install -D -m 644 "${repository_root}/themes/OMZ-LICENSE.txt" "${stage}/share/wsh/themes/OMZ-LICENSE.txt"
install -D -m 644 "${repository_root}/themes/robbyrussell.toml" "${stage}/share/wsh/themes/robbyrussell.toml"
install -D -m 644 "${repository_root}/themes/agnoster.toml" "${stage}/share/wsh/themes/agnoster.toml"
install -D -m 644 "${repository_root}/themes/minimal.toml" "${stage}/share/wsh/themes/minimal.toml"
install -D -m 644 "${repository_root}/themes/wakamex.toml" "${stage}/share/wsh/themes/wakamex.toml"

if [[ -n $(find "$stage" -type l -print -quit) ]]; then
  print -u2 -- 'error: development payload contains a symbolic link'
  exit 1
fi

if jq -e 'has("native")' "$zsh_source_lock" >/dev/null; then
  find "$stage" -type f -exec chmod 644 {} +
  chmod 755 "${stage}"/bin/*
  identity=$(python3 "${script_dir}/native_manifest.py" create "$stage" "$zsh_source_lock")
  destination=${output_root}/${identity}
  if [[ -e $destination ]]; then
    python3 "${script_dir}/native_manifest.py" verify "$destination" >/dev/null
    rm -rf -- "$stage"
  else
    mv -- "$stage" "$destination"
  fi
  trap - EXIT INT TERM
  print -r -- "$destination"
  exit 0
fi
