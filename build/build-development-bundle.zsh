#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly zsh_root=${repository_root}/build/out/zsh-5.9.2
readonly output_root=${repository_root}/bundles

for command in cargo cp find gcc git head install jq ld mktemp mv rm rustc sha256sum sort stat; do
  if (( ! $+commands[$command] )); then
    print -u2 -- "error: required command not found: ${command}"
    exit 1
  fi
done

"${script_dir}/build-zsh.zsh" >/dev/null
cd "$repository_root"
cargo build --release --locked --workspace

mkdir -p -- "$output_root"
stage=$(mktemp -d "${output_root}/.development.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT INT TERM
chmod 700 "$stage"

install -D -m 755 "${zsh_root}/bin/zsh" "${stage}/bin/zsh"
install -D -m 755 "${repository_root}/target/release/wsh-runtime" "${stage}/bin/wsh-runtime"
cp -R -- "${zsh_root}/lib" "$stage/lib"
mkdir -p -- "${stage}/share/zsh/5.9.2"
cp -R -- "${zsh_root}/share/zsh/5.9.2/functions" "${stage}/share/zsh/5.9.2/functions"
install -D -m 644 "${repository_root}/integration/integration.zsh" "${stage}/share/wsh/integration.zsh"
install -D -m 644 "${repository_root}/integration/zdotdir.zshenv" "${stage}/share/wsh/zdotdir/.zshenv"
install -D -m 644 "${repository_root}/integration/zdotdir.zshrc" "${stage}/share/wsh/zdotdir/.zshrc"
install -D -m 644 "${repository_root}/schemas/bundle.schema.json" "${stage}/share/wsh/schemas/bundle.schema.json"
install -D -m 644 "${repository_root}/schemas/theme.schema.json" "${stage}/share/wsh/schemas/theme.schema.json"
install -D -m 644 "${repository_root}/themes/minimal.toml" "${stage}/share/wsh/themes/minimal.toml"

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

source_revision=$(git rev-parse HEAD)
if [[ -n $(git status --short --untracked-files=all) ]]; then
  source_revision="${source_revision}+dirty"
fi
lockfile_sha256=$(sha256sum Cargo.lock)
lockfile_sha256=${lockfile_sha256%% *}
rust_compiler=$(rustc --version)
c_compiler=$(gcc --version | head -n 1)
linker=$(ld --version | head -n 1)

jq -n \
  --arg release_id "development-${source_revision}" \
  --arg source_revision "$source_revision" \
  --arg lockfile_sha256 "$lockfile_sha256" \
  --arg rust_compiler "$rust_compiler" \
  --arg c_compiler "$c_compiler" \
  --arg linker "$linker" \
  --slurpfile files "$file_records" \
  '{
    schema_version:1,
    status:"development",
    release_id:$release_id,
    target:"x86_64-unknown-linux-gnu",
    minimum_manager_version:"0.1.0",
    zsh:{
      version:"5.9.2",
      source_archive:"https://downloads.sourceforge.net/project/zsh/zsh/5.9.2/zsh-5.9.2.tar.xz",
      source_sha256:"36fa734374b44783582cec09bcd67822e2f992c779ec1624ab5596df078d2f81",
      signer_fingerprint:"7CA7ECAAF06216B90F894146ACF8146CAE8CBBC4",
      source_revision:"zsh-5.9.2",
      patches:[],
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
    requirements:{dynamic_libraries:["libc.so.6","libcap.so.2","libm.so.6","libncursesw.so.6","libpcre2-8.so.0","libtinfo.so.6"],minimum_glibc:null},
    files:$files
  }' > "${stage}/manifest.json"
rm -- "$file_records"

manifest_sha256=$(sha256sum "${stage}/manifest.json")
manifest_sha256=${manifest_sha256%% *}
destination=${output_root}/${manifest_sha256}
if [[ -e $destination ]]; then
  "${repository_root}/target/release/wsh" bundle verify "$destination" >/dev/null
  rm -rf -- "$stage"
  trap - EXIT INT TERM
  print -r -- "$destination"
  exit 0
fi
mv -- "$stage" "$destination"
trap - EXIT INT TERM
print -r -- "$destination"
