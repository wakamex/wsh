#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly source_lock=${WSH_ZSH_SOURCE_LOCK:-${script_dir}/zsh-sources/zsh-cad0d67c.json}
readonly cache_dir=${repository_root}/build/cache
readonly output_root=${WSH_ZSH_OUTPUT_ROOT:-${repository_root}/build/out}

for command in awk curl gcc getconf jq make sha256sum tar; do
  if (( ! $+commands[$command] )); then
    print -u2 -- "error: required command not found: ${command}"
    exit 1
  fi
done

[[ -f $source_lock ]] || {
  print -u2 -- "error: Zsh source lock not found: ${source_lock}"
  exit 1
}
jq -e '
  .schema_version == 1 and
  (.id | type == "string" and length > 0) and
  (.mode == "signed-release" or .mode == "canonical-commit") and
  (.version | type == "string" and length > 0) and
  (.output_name | type == "string" and test("^zsh-[A-Za-z0-9._-]+$")) and
  (.repository | type == "string" and startswith("https://")) and
  (.archive_name | type == "string" and test("^zsh-[A-Za-z0-9._-]+\\.tar\\.(xz|gz)$")) and
  (.archive_url | type == "string" and startswith("https://")) and
  (.archive_sha256 | type == "string" and test("^[0-9a-f]{64}$")) and
  (.source_revision | type == "string" and length > 0) and
  (.preconfigure | type == "boolean") and
  (.source_patches | type == "array") and
  (all(.source_patches[];
    (.path | type == "string" and test("^build/zsh-patches/[A-Za-z0-9._-]+\\.patch$")) and
    (.sha256 | type == "string" and test("^[0-9a-f]{64}$")))) and
  (.test_patches | type == "array") and
  (all(.test_patches[];
    (.path | type == "string" and test("^build/zsh-test-patches/[A-Za-z0-9._-]+\\.patch$")) and
    (.sha256 | type == "string" and test("^[0-9a-f]{64}$")))) and
  (if .mode == "signed-release" then
    (.source_tree == null and (.signature_url | type == "string" and startswith("https://")) and (.signer_fingerprint | type == "string" and test("^[0-9A-F]{40}$")) and (.key_url | type == "string" and startswith("https://")) and .preconfigure == false)
  else
    ((.source_revision | test("^[0-9a-f]{40}$")) and (.source_tree | type == "string" and test("^[0-9a-f]{40}$")) and .signature_url == null and .signer_fingerprint == null and .key_url == null and .preconfigure == true)
  end)
' "$source_lock" >/dev/null || {
  print -u2 -- "error: invalid Zsh source lock: ${source_lock}"
  exit 1
}

readonly source_mode=$(jq -er '.mode' "$source_lock")
readonly zsh_version=$(jq -er '.version' "$source_lock")
readonly output_name=$(jq -er '.output_name' "$source_lock")
readonly archive_name=$(jq -er '.archive_name' "$source_lock")
readonly source_url=$(jq -er '.archive_url' "$source_lock")
readonly source_sha256=$(jq -er '.archive_sha256' "$source_lock")
readonly preconfigure=$(jq -er '.preconfigure' "$source_lock")
readonly source_patch_count=$(jq -er '.source_patches | length' "$source_lock")
readonly test_patch_count=$(jq -er '.test_patches | length' "$source_lock")
source_lock_sha256=$(sha256sum "$source_lock")
readonly source_lock_sha256=${source_lock_sha256%% *}
readonly output_dir=${output_root}/${output_name}
readonly archive=${cache_dir}/${archive_name}

if [[ $preconfigure == true ]]; then
  for command in autoconf autoheader; do
    if (( ! $+commands[$command] )); then
      print -u2 -- "error: required command not found for development source: ${command}"
      exit 1
    fi
  done
fi
if (( source_patch_count + test_patch_count > 0 )) && (( ! $+commands[patch] )); then
  print -u2 -- "error: required command not found for Zsh patches: patch"
  exit 1
fi

verify_patch() {
  local patch_path=$1 expected_sha256=$2 scope=$3
  local absolute_path=${repository_root}/${patch_path}
  [[ -f $absolute_path ]] || {
    print -u2 -- "error: Zsh ${scope} patch not found: ${patch_path}"
    return 1
  }
  print -r -- "${expected_sha256}  ${absolute_path}" | sha256sum --check --status || {
    print -u2 -- "error: Zsh ${scope} patch digest mismatch: ${patch_path}"
    return 1
  }
  if [[ $scope == test ]]; then
    awk '
      /^(---|\+\+\+) / && $2 !~ /^(a|b)\/Test\// { invalid = 1 }
      END { exit invalid }
    ' "$absolute_path" || {
      print -u2 -- "error: Zsh test patch changes a path outside Test/: ${patch_path}"
      return 1
    }
  fi
}

while IFS=$'\t' read -r source_patch_path source_patch_sha256; do
  verify_patch "$source_patch_path" "$source_patch_sha256" source
done < <(jq -r '.source_patches[] | [.path, .sha256] | @tsv' "$source_lock")
while IFS=$'\t' read -r test_patch_path test_patch_sha256; do
  verify_patch "$test_patch_path" "$test_patch_sha256" test
done < <(jq -r '.test_patches[] | [.path, .sha256] | @tsv' "$source_lock")

mkdir -p -- "$cache_dir" "$output_root"

if [[ -x ${output_dir}/bin/zsh ]]; then
  [[ -r ${output_dir}/.wsh-source-lock.sha256 && $(<${output_dir}/.wsh-source-lock.sha256) == $source_lock_sha256 ]] || {
    print -u2 -- "error: existing output was built from a different Zsh source lock: ${output_dir}"
    exit 1
  }
  actual_version=$(${output_dir}/bin/zsh --version)
  if [[ $actual_version == "zsh ${zsh_version}"* ]]; then
    print -r -- "$output_dir"
    exit 0
  fi
  print -u2 -- "error: existing output has unexpected version: ${actual_version}"
  exit 1
fi

curl --fail --location --retry 3 --output "$archive" "$source_url"
print -r -- "${source_sha256}  ${archive}" | sha256sum --check --status

work_dir=$(mktemp -d "${output_root}/.${output_name}.XXXXXX")
cleanup_work_dir() {
  if [[ -n ${WSH_KEEP_FAILED_BUILD:-} ]]; then
    print -u2 -- "preserved failed Zsh build: $work_dir"
  else
    rm -rf -- "$work_dir"
  fi
}
trap cleanup_work_dir EXIT INT TERM
chmod 700 "$work_dir"

if [[ $source_mode == signed-release ]]; then
  if (( ! $+commands[gpg] )); then
    print -u2 -- 'error: required command not found for signed source: gpg'
    exit 1
  fi
  readonly signature_url=$(jq -er '.signature_url' "$source_lock")
  readonly signer_fingerprint=$(jq -er '.signer_fingerprint' "$source_lock")
  readonly key_url=$(jq -er '.key_url' "$source_lock")
  readonly signature=${archive}.asc
  curl --fail --location --retry 3 --output "$signature" "$signature_url"
  curl --fail --location --retry 3 --output "${work_dir}/signing-key.asc" "$key_url"
  mkdir -- "${work_dir}/gnupg"
  chmod 700 "${work_dir}/gnupg"
  gpg --batch --quiet --homedir "${work_dir}/gnupg" --import "${work_dir}/signing-key.asc"

  imported_fingerprint=$(gpg --batch --homedir "${work_dir}/gnupg" --with-colons --fingerprint "$signer_fingerprint" | awk -F: '$1 == "fpr" { print $10; exit }')
  if [[ $imported_fingerprint != $signer_fingerprint ]]; then
    print -u2 -- "error: signing key fingerprint mismatch"
    exit 1
  fi

  signature_status=$(gpg --batch --homedir "${work_dir}/gnupg" --status-fd 1 --verify "$signature" "$archive" 2>/dev/null)
  if [[ $signature_status != *"[GNUPG:] VALIDSIG ${signer_fingerprint} "* ]]; then
    print -u2 -- "error: source signature was not made by ${signer_fingerprint}"
    exit 1
  fi
fi

mkdir -- "${work_dir}/source" "${work_dir}/dest"
tar --extract --file "$archive" --directory "${work_dir}/source" --strip-components=1

cd "${work_dir}/source"
if (( source_patch_count > 0 )); then
  source_patch=
  while IFS=$'\t' read -r source_patch_path source_patch_sha256; do
    source_patch=${repository_root}/${source_patch_path}
    patch --batch --forward --strip=1 < "$source_patch"
  done < <(jq -r '.source_patches[] | [.path, .sha256] | @tsv' "$source_lock")
fi
if [[ $preconfigure == true ]]; then
  ./Util/preconfig
fi
./configure \
  --prefix="$output_dir" \
  --enable-cap \
  --enable-multibyte \
  --enable-pcre
make -j "${WSH_BUILD_JOBS:-$(getconf _NPROCESSORS_ONLN)}"
if (( test_patch_count > 0 )); then
  test_patch=
  while IFS=$'\t' read -r test_patch_path test_patch_sha256; do
    test_patch=${repository_root}/${test_patch_path}
    patch --batch --forward --strip=1 < "$test_patch"
  done < <(jq -r '.test_patches[] | [.path, .sha256] | @tsv' "$source_lock")
fi
make check
make install.bin install.modules install.fns DESTDIR="${work_dir}/dest"

readonly staged_install="${work_dir}/dest${output_dir}"
if [[ ! -x ${staged_install}/bin/zsh ]]; then
  print -u2 -- "error: build did not produce bin/zsh"
  exit 1
fi
print -r -- "$source_lock_sha256" >| "${staged_install}/.wsh-source-lock.sha256"

mv -- "$staged_install" "$output_dir"
trap - EXIT INT TERM
rm -rf -- "$work_dir"

actual_version=$(${output_dir}/bin/zsh --version)
if [[ $actual_version != "zsh ${zsh_version}"* ]]; then
  print -u2 -- "error: built shell has unexpected version: ${actual_version}"
  exit 1
fi

print -r -- "$output_dir"
