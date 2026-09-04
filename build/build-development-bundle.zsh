#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly zsh_source_lock=${WSH_ZSH_SOURCE_LOCK:-${script_dir}/zsh-sources/zsh-cad0d67c.json}
readonly zsh_output_root=${WSH_ZSH_OUTPUT_ROOT:-${repository_root}/build/out}
readonly output_root=${WSH_BUNDLE_OUTPUT_ROOT:-${repository_root}/bundles}
readonly cargo_target_dir=${CARGO_TARGET_DIR:-${repository_root}/target}
readonly bundle_status=${WSH_BUNDLE_STATUS:-development}
readonly requested_release_id=${WSH_RELEASE_ID:-}

for command in cargo cp find git head install jq ld mktemp mv readelf rm rustc sed sha256sum sort stat; do
  if (( ! $+commands[$command] )); then
    print -u2 -- "error: required command not found: ${command}"
    exit 1
  fi
done

readonly zsh_version=$(jq -er '.version' "$zsh_source_lock")
readonly zsh_output_name=$(jq -er '.output_name' "$zsh_source_lock")
readonly zsh_source_mode=$(jq -er '.mode' "$zsh_source_lock")
readonly zsh_source_repository=$(jq -er '.repository' "$zsh_source_lock")
readonly zsh_source_archive=$(jq -er '.archive_url' "$zsh_source_lock")
readonly zsh_source_sha256=$(jq -er '.archive_sha256' "$zsh_source_lock")
readonly zsh_signer_fingerprint=$(jq -r '.signer_fingerprint // ""' "$zsh_source_lock")
readonly zsh_source_revision=$(jq -er '.source_revision' "$zsh_source_lock")
readonly zsh_source_tree=$(jq -r '.source_tree // ""' "$zsh_source_lock")
readonly zsh_test_patches=$(jq -c '[.test_patches[].sha256]' "$zsh_source_lock")
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
cd "$repository_root"
cargo build --release --locked --workspace

mkdir -p -- "$output_root"
stage=$(mktemp -d "${output_root}/.development.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT INT TERM
chmod 700 "$stage"

install -D -m 755 "${zsh_root}/bin/zsh" "${stage}/bin/zsh"
install -D -m 755 "${cargo_target_dir}/release/wsh-runtime" "${stage}/bin/wsh-runtime"
cp -R -- "${zsh_root}/lib" "$stage/lib"
mkdir -p -- "${stage}/share/zsh/${zsh_version}"
cp -R -- "${zsh_root}/share/zsh/${zsh_version}/functions" "${stage}/share/zsh/${zsh_version}/functions"
install -D -m 644 "${repository_root}/integration/integration.zsh" "${stage}/share/wsh/integration.zsh"
install -D -m 644 "${repository_root}/integration/history-substring-search.zsh" "${stage}/share/wsh/defaults/history-substring-search.zsh"
install -D -m 644 "${repository_root}/third_party/zsh-history-substring-search/zsh-history-substring-search.zsh" "${stage}/share/wsh/defaults/zsh-history-substring-search.zsh"
install -D -m 644 "${repository_root}/third_party/zsh-history-substring-search/oh-my-zsh-history-substring-search.zsh" "${stage}/share/wsh/defaults/known-oh-my-zsh-history-substring-search.zsh"
install -D -m 644 "${repository_root}/third_party/zsh-history-substring-search/PROVENANCE.md" "${stage}/share/wsh/defaults/zsh-history-substring-search-PROVENANCE.md"
install -D -m 644 "${repository_root}/third_party/zsh-history-substring-search/OH-MY-ZSH-LICENSE.txt" "${stage}/share/wsh/defaults/zsh-history-substring-search-OH-MY-ZSH-LICENSE.txt"
(cd "${stage}/share/wsh/defaults" && "${stage}/bin/zsh" -fc 'zcompile zsh-history-substring-search.zsh.zwc zsh-history-substring-search.zsh')
chmod 644 "${stage}/share/wsh/defaults/zsh-history-substring-search.zsh.zwc"
install -D -m 644 "${repository_root}/integration/autosuggestions.zsh" "${stage}/share/wsh/defaults/autosuggestions.zsh"
install -D -m 644 "${repository_root}/third_party/zsh-autosuggestions/zsh-autosuggestions.zsh" "${stage}/share/wsh/defaults/zsh-autosuggestions.zsh"
install -D -m 644 "${repository_root}/third_party/zsh-autosuggestions/PROVENANCE.md" "${stage}/share/wsh/defaults/zsh-autosuggestions-PROVENANCE.md"
install -D -m 644 "${repository_root}/third_party/zsh-autosuggestions/LICENSE" "${stage}/share/wsh/defaults/zsh-autosuggestions-LICENSE"
(cd "${stage}/share/wsh/defaults" && "${stage}/bin/zsh" -fc 'zcompile zsh-autosuggestions.zsh.zwc zsh-autosuggestions.zsh')
chmod 644 "${stage}/share/wsh/defaults/zsh-autosuggestions.zsh.zwc"
install -D -m 644 "${repository_root}/integration/syntax-highlighting.zsh" "${stage}/share/wsh/defaults/syntax-highlighting.zsh"
cp -R -- "${repository_root}/third_party/zsh-syntax-highlighting" "${stage}/share/wsh/defaults/zsh-syntax-highlighting"
(cd "${stage}/share/wsh/defaults/zsh-syntax-highlighting" && "${stage}/bin/zsh" -fc 'zcompile zsh-syntax-highlighting.zsh.zwc zsh-syntax-highlighting.zsh; for source in highlighters/*/*-highlighter.zsh; do zcompile ${source}.zwc $source; done')
find "${stage}/share/wsh/defaults/zsh-syntax-highlighting" -type f -exec chmod 644 {} +
install -D -m 644 "${repository_root}/integration/zdotdir.zshenv" "${stage}/share/wsh/zdotdir/.zshenv"
install -D -m 644 "${repository_root}/integration/zdotdir.zprofile" "${stage}/share/wsh/zdotdir/.zprofile"
install -D -m 644 "${repository_root}/integration/zdotdir.zshrc" "${stage}/share/wsh/zdotdir/.zshrc"
install -D -m 644 "${repository_root}/integration/zdotdir.zlogin" "${stage}/share/wsh/zdotdir/.zlogin"
install -D -m 644 "${repository_root}/schemas/bundle.schema.json" "${stage}/share/wsh/schemas/bundle.schema.json"
install -D -m 644 "${repository_root}/schemas/theme.schema.json" "${stage}/share/wsh/schemas/theme.schema.json"
install -D -m 644 "${repository_root}/themes/minimal.toml" "${stage}/share/wsh/themes/minimal.toml"
install -D -m 644 "${repository_root}/themes/wakamex.toml" "${stage}/share/wsh/themes/wakamex.toml"

if [[ -n $(find "$stage" -type l -print -quit) ]]; then
  print -u2 -- 'error: development payload contains a symbolic link'
  exit 1
fi

file_records=${stage}/.file-records.jsonl
: >| "$file_records"
while IFS= read -r -d '' payload; do
  relative=${payload#${stage}/}
  [[ $relative == .file-records.jsonl ]] && continue
  octal_mode=$(stat -c %a -- "$payload")
  integer_mode=$(( 8#${octal_mode} ))
  size=$(stat -c %s -- "$payload")
  digest=$(sha256sum -- "$payload")
  digest=${digest%% *}
  jq -cn \
    --arg path "$relative" \
    --argjson mode "$integer_mode" \
    --argjson size "$size" \
    --arg sha256 "$digest" \
    '{path:$path,kind:"file",mode:$mode,size:$size,sha256:$sha256}' >> "$file_records"
done < <(find "$stage" -type f -print0 | sort -z)

source_revision=${WSH_SOURCE_REVISION:-}
if [[ -z $source_revision ]]; then
  source_revision=$(git rev-parse HEAD)
  if [[ -n $(git status --short --untracked-files=all) ]]; then
    source_revision="${source_revision}+dirty"
  fi
fi
case $bundle_status in
  development)
    [[ -z $requested_release_id ]] || {
      print -u2 -- 'error: a development bundle cannot set WSH_RELEASE_ID'
      exit 1
    }
    release_id=development-${source_revision}
    ;;
  release)
    [[ $requested_release_id =~ '^v[0-9]+\.[0-9]+\.[0-9]+$' ]] || {
      print -u2 -- 'error: a release bundle requires WSH_RELEASE_ID=vMAJOR.MINOR.PATCH'
      exit 1
    }
    [[ $source_revision =~ '^[0-9a-f]{40}$' ]] || {
      print -u2 -- 'error: a release bundle requires an exact clean source revision'
      exit 1
    }
    release_id=$requested_release_id
    ;;
  *)
    print -u2 -- "error: unsupported bundle status: $bundle_status"
    exit 1
    ;;
esac
readonly release_id
lockfile_sha256=$(sha256sum Cargo.lock)
lockfile_sha256=${lockfile_sha256%% *}
rust_compiler=$(rustc --version)
c_compiler_command=${CC:-gcc}
if [[ $c_compiler_command == */* ]]; then
  [[ -x $c_compiler_command ]] || {
    print -u2 -- "error: C compiler not found: ${c_compiler_command}"
    exit 1
  }
elif (( ! $+commands[$c_compiler_command] )); then
  print -u2 -- "error: C compiler not found: ${c_compiler_command}"
  exit 1
fi
c_compiler=$(${c_compiler_command} --version | head -n 1)
linker=$(ld --version | head -n 1)
minimum_glibc=${WSH_MINIMUM_GLIBC:-}
builder_base_image=${WSH_BUILDER_BASE_IMAGE:-}
builder_package_lock_sha256=${WSH_BUILDER_PACKAGE_LOCK_SHA256:-}
rust_toolchain_sha256=${WSH_RUST_TOOLCHAIN_SHA256:-}
source_date_epoch=${SOURCE_DATE_EPOCH:-}
build_lang=${LANG:-C}
build_lc_all=${LC_ALL:-${LANG:-C}}
build_timezone=${TZ:-UTC}
build_jobs=${WSH_BUILD_JOBS:-${CARGO_BUILD_JOBS:-auto}}
dynamic_libraries=$(find "$stage" -type f -exec readelf -d {} \; 2>/dev/null \
  | sed -n 's/.*Shared library: \[\(.*\)\]/\1/p' \
  | sort -u \
  | jq -R . \
  | jq -s .)

jq -n \
  --arg status "$bundle_status" \
  --arg release_id "$release_id" \
  --arg source_revision "$source_revision" \
  --arg lockfile_sha256 "$lockfile_sha256" \
  --arg rust_compiler "$rust_compiler" \
  --arg c_compiler "$c_compiler" \
  --arg linker "$linker" \
  --arg minimum_glibc "$minimum_glibc" \
  --arg builder_base_image "$builder_base_image" \
  --arg builder_package_lock_sha256 "$builder_package_lock_sha256" \
  --arg rust_toolchain_sha256 "$rust_toolchain_sha256" \
  --arg source_date_epoch "$source_date_epoch" \
  --arg build_lang "$build_lang" \
  --arg build_lc_all "$build_lc_all" \
  --arg build_timezone "$build_timezone" \
  --arg build_jobs "$build_jobs" \
  --arg zsh_version "$zsh_version" \
  --arg zsh_source_mode "$zsh_source_mode" \
  --arg zsh_source_repository "$zsh_source_repository" \
  --arg zsh_source_archive "$zsh_source_archive" \
  --arg zsh_source_sha256 "$zsh_source_sha256" \
  --arg zsh_signer_fingerprint "$zsh_signer_fingerprint" \
  --arg zsh_source_revision "$zsh_source_revision" \
  --arg zsh_source_tree "$zsh_source_tree" \
  --argjson zsh_test_patches "$zsh_test_patches" \
  --argjson dynamic_libraries "$dynamic_libraries" \
  --slurpfile files "$file_records" \
  '{
    schema_version:1,
    status:$status,
    release_id:$release_id,
    target:"x86_64-unknown-linux-gnu",
    minimum_manager_version:"0.1.0",
    builder:{
      base_image:(if $builder_base_image == "" then null else $builder_base_image end),
      package_lock_sha256:(if $builder_package_lock_sha256 == "" then null else $builder_package_lock_sha256 end),
      rust_toolchain_sha256:(if $rust_toolchain_sha256 == "" then null else $rust_toolchain_sha256 end),
      source_date_epoch:(if $source_date_epoch == "" then null else ($source_date_epoch | tonumber) end),
      environment:{lang:$build_lang,lc_all:$build_lc_all,tz:$build_timezone,build_jobs:$build_jobs}
    },
    zsh:{
      version:$zsh_version,
      source_mode:$zsh_source_mode,
      source_repository:$zsh_source_repository,
      source_archive:$zsh_source_archive,
      source_sha256:$zsh_source_sha256,
      signer_fingerprint:(if $zsh_signer_fingerprint == "" then null else $zsh_signer_fingerprint end),
      source_revision:$zsh_source_revision,
      source_tree:(if $zsh_source_tree == "" then null else $zsh_source_tree end),
      patches:$zsh_test_patches,
      configure_args:["--enable-cap","--enable-multibyte","--enable-pcre"],
      compiler:$c_compiler,
      linker:$linker
    },
    rust:{
      source_revision:$source_revision,
      lockfile_sha256:$lockfile_sha256,
      target:"x86_64-unknown-linux-gnu",
      compiler:$rust_compiler,
      profile:"release"
    },
    api_versions:{runtime_protocol:1,provider_schema:1,theme_schema:1,integration_api:1},
    entrypoints:{shell:"bin/zsh",runtime:"bin/wsh-runtime",integration:"share/wsh/integration.zsh",default_theme:"share/wsh/themes/minimal.toml"},
    requirements:{dynamic_libraries:$dynamic_libraries,minimum_glibc:(if $minimum_glibc == "" then null else $minimum_glibc end)},
    files:$files
  }' > "${stage}/manifest.json"
rm -- "$file_records"

manifest_sha256=$(sha256sum "${stage}/manifest.json")
manifest_sha256=${manifest_sha256%% *}
destination=${output_root}/${manifest_sha256}
if [[ -e $destination ]]; then
  "${cargo_target_dir}/release/wsh" bundle verify "$destination" >/dev/null
  rm -rf -- "$stage"
  trap - EXIT INT TERM
  print -r -- "$destination"
  exit 0
fi
mv -- "$stage" "$destination"
trap - EXIT INT TERM
print -r -- "$destination"
