#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail

readonly zsh_version=5.9.2
readonly archive_name="zsh-${zsh_version}.tar.xz"
readonly source_url="https://downloads.sourceforge.net/project/zsh/zsh/${zsh_version}/${archive_name}"
readonly signature_url="${source_url}.asc"
readonly source_sha256=36fa734374b44783582cec09bcd67822e2f992c779ec1624ab5596df078d2f81
readonly signer_fingerprint=7CA7ECAAF06216B90F894146ACF8146CAE8CBBC4
readonly key_url='https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x7CA7ECAAF06216B90F894146ACF8146CAE8CBBC4'

readonly script_dir=${0:A:h}
readonly repository_root=${script_dir:h}
readonly cache_dir=${repository_root}/build/cache
readonly output_root=${WSH_ZSH_OUTPUT_ROOT:-${repository_root}/build/out}
readonly output_dir=${output_root}/zsh-${zsh_version}
readonly archive=${cache_dir}/${archive_name}
readonly signature=${archive}.asc

for command in awk curl gcc getconf gpg make sha256sum tar; do
  if (( ! $+commands[$command] )); then
    print -u2 -- "error: required command not found: ${command}"
    exit 1
  fi
done

mkdir -p -- "$cache_dir" "$output_root"

if [[ -x ${output_dir}/bin/zsh ]]; then
  actual_version=$(${output_dir}/bin/zsh --version)
  if [[ $actual_version == "zsh ${zsh_version}"* ]]; then
    print -r -- "$output_dir"
    exit 0
  fi
  print -u2 -- "error: existing output has unexpected version: ${actual_version}"
  exit 1
fi

curl --fail --location --retry 3 --output "$archive" "$source_url"
curl --fail --location --retry 3 --output "$signature" "$signature_url"

print -r -- "${source_sha256}  ${archive}" | sha256sum --check --status

work_dir=$(mktemp -d "${output_root}/.zsh-${zsh_version}.XXXXXX")
cleanup_work_dir() {
  if [[ -n ${WSH_KEEP_FAILED_BUILD:-} ]]; then
    print -u2 -- "preserved failed Zsh build: $work_dir"
  else
    rm -rf -- "$work_dir"
  fi
}
trap cleanup_work_dir EXIT INT TERM
chmod 700 "$work_dir"

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

mkdir -- "${work_dir}/source" "${work_dir}/dest"
tar --extract --xz --file "$archive" --directory "${work_dir}/source" --strip-components=1

cd "${work_dir}/source"
./configure \
  --prefix="$output_dir" \
  --enable-cap \
  --enable-multibyte \
  --enable-pcre
make -j "${WSH_BUILD_JOBS:-$(getconf _NPROCESSORS_ONLN)}"
make check
make install DESTDIR="${work_dir}/dest"

readonly staged_install="${work_dir}/dest${output_dir}"
if [[ ! -x ${staged_install}/bin/zsh ]]; then
  print -u2 -- "error: build did not produce bin/zsh"
  exit 1
fi

mv -- "$staged_install" "$output_dir"
trap - EXIT INT TERM
rm -rf -- "$work_dir"

actual_version=$(${output_dir}/bin/zsh --version)
if [[ $actual_version != "zsh ${zsh_version}"* ]]; then
  print -u2 -- "error: built shell has unexpected version: ${actual_version}"
  exit 1
fi

print -r -- "$output_dir"
