# Local Git references supply provenance for upstream versions outside the catalog.
_wsh_plugin_git() {
  GIT_TERMINAL_PROMPT=0 GIT_NO_LAZY_FETCH=1 command timeout --kill-after=0.1s 1s \
    git --no-replace-objects --no-optional-locks "$@" 2>/dev/null
}

_wsh_plugin_git_recognized() {
  builtin emulate -L zsh -o no_aliases -o no_multibyte -o pipe_fail
  (( $# >= 2 && $+commands[git] && $+commands[timeout] && $+commands[head] )) || return 1
  local component=$1 root config line key url remote row base response header content
  local upstream branch handoff relative_path source candidate fd count size index
  local -a files expected fields requests header_fields
  local attempts=0
  shift
  for source in "$@"; do
    [[ -f $source && -r $source ]] || return 1
    files+=("${source:A}")
  done
  # Sentinel preserves paths and contents that end in a newline.
  root=$(_wsh_plugin_git -C ${files[1]:h} rev-parse --show-toplevel && builtin print -rn -- $'\x1e') || return 1
  root=${root%$'\n\x1e'}
  [[ -n $root && -d $root ]] || return 1
  config=$(_wsh_plugin_git -C $root config --get-regexp '^(remote\..*\.(url|promisor)|extensions\.partialclone)$' | command head -c 65537) || return 1
  (( $#config <= 65536 )) || return 1
  # Older Git versions can fetch missing objects implicitly. Refuse partial
  # clones before reading objects, independently of GIT_NO_LAZY_FETCH support.
  for line in "${(@f)config}"; do
    key=${line%% *}
    [[ $key != extensions.partialclone && $key != remote.*.promisor ]] || return 1
  done
  zmodload zsh/system 2>/dev/null || return 1
  for row in "${(@f)_WSH_PLUGIN_UPSTREAMS[$component]}"; do
    fields=("${(@s:|:)row}")
    (( $#fields == $#files + 3 )) || continue
    upstream=$fields[1] branch=$fields[2] handoff=$fields[3]
    expected=("${(@)fields[4,-1]}")
    index=1
    for relative_path in "$expected[@]"; do
      [[ $files[$index] == $root/$relative_path ]] || break
      (( ++index ))
    done
    (( index == $#files + 1 )) || continue
    for line in "${(@f)config}"; do
      key=${line%% *} url=${line#* }
      [[ $key == remote.*.url ]] || continue
      url=${url%/}; url=${url%.git}
      url=${url/#git@github.com:/https:\/\/github.com\/}
      url=${url/#ssh:\/\/git@github.com\//https:\/\/github.com\/}
      [[ ${(L)url} == ${(L)upstream} ]] || continue
      (( ++attempts <= 8 )) || return 1
      remote=${${key#remote.}%.url}
      base=$(_wsh_plugin_git -C $root merge-base HEAD refs/remotes/$remote/$branch) || continue
      [[ $base != *[^0-9a-f]* ]] && (( $#base == 40 || $#base == 64 )) || continue
      requests=()
      for relative_path in "$expected[@]"; do requests+=("$base:$relative_path"); done
      # Read raw blobs, bypassing index flags, clean filters and textconv. Bound
      # the aggregate response before storing it in a shell parameter.
      response=$(builtin print -rl -- "$requests[@]" | _wsh_plugin_git -C $root cat-file --batch | command head -c $(( $#files * (131072 + 256) )) && builtin print -rn -- $'\x1e') || continue
      response=${response%$'\x1e'}
      index=1
      for source in "$files[@]"; do
        header=${response%%$'\n'*}
        header_fields=("${(@s: :)header}")
        (( $#header_fields == 3 )) && [[ $header_fields[2] == blob && $header_fields[3] == <-> ]] || break
        size=$header_fields[3]
        (( size > 0 && size <= 131072 )) || break
        response=${response#*$'\n'}
        (( $#response >= size + 1 )) && [[ $response[$((size+1))] == $'\n' ]] || break
        content=$response[1,$size]
        response=$response[$((size+2)),-1]
        candidate= count=0
        sysopen -r -o cloexec -u fd $source || break
        sysread -i $fd -s $((size+1)) -c count candidate || true
        builtin exec {fd}<&-
        (( count == size )) && [[ $candidate == $content ]] || break
        (( ++index ))
      done
      if (( index == $#files + 1 )) && [[ -z $response ]]; then
        _WSH_PLUGIN_HANDOFF=$handoff
        return 0
      fi
    done
  done
  return 1
}
