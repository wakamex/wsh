#!/usr/bin/env zsh

emulate -L zsh
setopt errexit nounset pipefail
zmodload zsh/datetime

local -i iterations=${1:-10000}
[[ $iterations == <1-> ]] || {
  print -u2 -- 'usage: benchmark-hex-decode.zsh [POSITIVE_ITERATIONS]'
  exit 2
}

decode_byte_loop() {
  emulate -L zsh
  local LC_ALL=C value=$1 output='' byte character
  while [[ -n $value ]]; do
    byte=$value[1,2]
    value=$value[3,-1]
    printf -v character '%b' "\\x${byte}"
    output+=$character
  done
  REPLY=$output
}

decode_whole_string() {
  emulate -L zsh
  setopt extendedglob
  local LC_ALL=C value=$1 escaped
  local -a match mbegin mend
  escaped=${value//(#b)(??)/\\x${match[1]}}
  printf -v REPLY '%b' "$escaped"
}

readonly prompt_hex=1b5b33346d666978747572651b5b33396d201b5b33356d206769743a6d61696e201b5b33396d1b5b33326d251b5b33396d20
local -a labels=(byte-loop whole-string)
local -a implementation_names=(decode_byte_loop decode_whole_string)
local -a order
local block label function
local -i index position repetition
local -F started elapsed mean_us

print -r -- $'block\tposition\tvariant\trepetition\titerations\tmean_us'
for block in forward reverse; do
  if [[ $block == forward ]]; then
    order=(1 2)
  else
    order=(2 1)
  fi
  position=0
  for index in $order; do
    (( position += 1 ))
    label=$labels[$index]
    function=$implementation_names[$index]
    repeat 100 $function $prompt_hex
    for repetition in {1..5}; do
      started=$EPOCHREALTIME
      repeat $iterations $function $prompt_hex
      elapsed=$(( EPOCHREALTIME - started ))
      mean_us=$(( elapsed * 1000000 / iterations ))
      printf '%s\t%d\t%s\t%d\t%d\t%.3f\n' $block $position $label $repetition $iterations $mean_us
    done
  done
done
