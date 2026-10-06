#!/usr/bin/env zsh
# Interrupts during an always block must propagate, as the Zsh manual states;
# TRY_BLOCK_INTERRUPT=0 still cancels one from the try block.
emulate -L zsh
setopt errexit nounset pipefail
readonly binary=${1:?usage: interrupt-propagation.zsh BINARY}
check() {
  local name=$1 code=$2 expected=$3 actual
  actual=$(timeout 10 $binary -fi -c "$code" 2>&1) || true
  [[ $actual == $expected ]] || { print -u2 -- "FAIL: $name: expected '$expected', got '$actual'"; exit 1 }
}
check 'interrupt in always block' '{ true } always { kill -INT $$ }; print survived' ''
check 'interrupt in try block' '{ kill -INT $$; true } always { : }; print survived' ''
check 'TRY_BLOCK_INTERRUPT reset' '{ kill -INT $$; true } always { TRY_BLOCK_INTERRUPT=0 }; print survived' 'survived'
check 'no interrupt' '{ true } always { : }; print survived' 'survived'
print 'PASS: interrupts propagate from always blocks and TRY_BLOCK_INTERRUPT resets them'
