#!/usr/bin/env zsh

builtin emulate -L zsh -o no_aliases -o err_return -o pipe_fail

readonly root=${0:A:h:h}
readonly evidence=$root/benchmarks/zcompile-reproducibility-2026-09-04
readonly accepted_revision=45c220a1c50a664db191549eba321b1f465a4858
readonly patch_digest=d1da8d32b8afa27bb0516c81f63345ea1196edf177bdae151fe9f2ad617776a6
readonly payload_path=share/wsh/defaults/zsh-syntax-highlighting/highlighters/line/line-highlighter.zsh.zwc
readonly temporary=$(mktemp -d /var/tmp/wsh-zcompile-evidence.XXXXXX)
trap 'command rm -rf -- $temporary' EXIT INT TERM

(builtin cd -q -- $evidence && sha256sum -c files.sha256 >/dev/null)

result_value() {
  local key=$1
  sed -n "s/^${key}=//p" $evidence/result.txt
}

verify_git_object() {
  local file=$1 expected=$2
  local actual=$(git -C $root show ${accepted_revision}:${file} | sha256sum)
  [[ ${actual%% *} == $expected ]] || {
    print -u2 -- "error: accepted compiled-function input changed: ${file}"
    exit 1
  }
}

[[ $(result_value source_revision) == $accepted_revision ]]
[[ $(result_value byte_identical) == 1 ]]
[[ $(result_value archive_a_sha256) == $(result_value archive_b_sha256) ]]
[[ $(result_value manifest_a_sha256) == $(result_value manifest_b_sha256) ]]
[[ $(result_value launcher_a_sha256) == $(result_value launcher_b_sha256) ]]
[[ $(result_value installer_a_sha256) == $(result_value installer_b_sha256) ]]
[[ $(result_value bootstrap_a_sha256) == $(result_value bootstrap_b_sha256) ]]
[[ $(result_value manifest_a_sha256) == $(sha256sum $evidence/manifest.json | cut -d ' ' -f 1) ]]
[[ $(jq -r --arg digest $patch_digest '.zsh.patches | index($digest) != null' $evidence/manifest.json) == true ]]

for worker in a b; do
  grep -Fqx 'PASS: identical Zsh source compiles byte-identically in isolated directories' $evidence/worker-${worker}.log
  grep -Fq 'PASS: relocated development bundle' $evidence/worker-${worker}.log
done
grep -Fqx '75 successful test scripts, 0 failures, 2 skipped' $evidence/zsh-upstream.log

[[ $(jq -r --arg path $payload_path '.files[] | select(.path == $path) | .sha256' $evidence/failed-worker-a.manifest.json) == d5f2768e763c90dd34e12ed168b1b07f608f2dccf95f9c2d0fe8bc0923a0dc98 ]]
[[ $(jq -r --arg path $payload_path '.files[] | select(.path == $path) | .sha256' $evidence/failed-worker-b.manifest.json) == e7404267c958facec01acc67b49d54416132994db176d1de3a17b74e6159fa2f ]]
jq --arg path $payload_path '(.files[] | select(.path == $path) | .sha256) = "normalized"' $evidence/failed-worker-a.manifest.json > $temporary/a.json
jq --arg path $payload_path '(.files[] | select(.path == $path) | .sha256) = "normalized"' $evidence/failed-worker-b.manifest.json > $temporary/b.json
diff -u $temporary/a.json $temporary/b.json

verify_git_object build/zsh-patches/cad0d67c-zcompile-padding.patch $patch_digest
verify_git_object build/zsh-sources/zsh-cad0d67c.json 519804c62a590d37f4a17d75070da89551adb4aa69d43780a9e0b75092362c62
verify_git_object tests/zcompile-reproducibility.zsh 729db2a63d374d3b76c2555c566f328cb22e93176373cb882703753db6dfd3a8
verify_git_object build/test-development-bundle.zsh d72b699f23f6095c507ec30dbbc6db20ac073e9d833ed99f1cebdd0948391c50
source_lock_digest=$(git -C $root show ${accepted_revision}:build/zsh-sources/zsh-cad0d67c.json | jq -r --arg digest $patch_digest '.source_patches[] | select(.sha256 == $digest) | .sha256')
[[ $source_lock_digest == $patch_digest ]]

print -r -- 'PASS: failed manifests isolate Zsh dump padding and patched isolated builds are byte-identical'
