#!/usr/bin/env python3
"""Compare bounded native header reads with Zsh's authoritative read builtin."""
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

BUNDLE,PROTO,OUT=[Path(x).resolve() for x in sys.argv[1:]];OUT.mkdir(parents=True)
source=(PROTO/'compinit').read_text();start=source.index('      if [[ $_i_bulk == yes ]]');end=source.index('      _i_tag=$_i_line[1]',start);candidate=source[start:end]
script=OUT/'read.zsh';script.write_text('''zmodload zsh/system
setopt extendedglob
typeset _i_bulk=yes _i_file _i_fd _i_header
typeset -a _i_line
for _i_file in "$1"/*(N); do
  if [[ $2 == candidate ]]; then
'''+candidate+'''
  else
    IFS=$' \\t' read -rA _i_line < $_i_file
  fi
  print -r -- "${_i_file:t}:${#_i_line}:${(j:|:)${(@qqqq)_i_line}}"
done
''')
files=OUT/'files';files.mkdir();cases=[b'',b'\n',b'\r\n',b'#compdef git\n',b' #compdef\t  a\\b "quoted name" \'literal\' \t\n',b'#compdef a\0b\n',b'#compdef \xff\n']
for size in [4094,4095,4096,4097,16384]:
    cases.extend([b'#'+b'a'*size+b'\nignored',b'#compdef '+b'b'*size])
rng=random.Random(20260909)
for _ in range(2000):cases.append(bytes(rng.randrange(256) for _ in range(rng.randrange(192))))
for index,data in enumerate(cases):(files/f'{index:05}').write_bytes(data)
outputs={}
for mode in ['control','candidate']:
    result=subprocess.run([BUNDLE/'bin/wsh','-df',script,files,mode],env=dict(PATH='/usr/bin:/bin',HOME=str(OUT),LC_ALL='C.UTF-8'),capture_output=True,timeout=20)
    assert result.returncode==0 and not result.stderr,(mode,result.stderr)
    outputs[mode]=result.stdout;(OUT/(mode+'.stdout')).write_bytes(result.stdout)
passed=outputs['control']==outputs['candidate']
(OUT/'results.json').write_text(json.dumps(dict(cases=len(cases),passed=passed,source_sha256=hashlib.sha256(source.encode()).hexdigest()),indent=2)+'\n')
if not passed:
    for a,b in zip(outputs['control'].splitlines(),outputs['candidate'].splitlines()):
        if a!=b:print(a,b);break
assert passed
print(f'PASS: {len(cases)} exact header-field comparisons including bounded-read fallback')
