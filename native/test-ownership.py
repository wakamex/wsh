#!/usr/bin/env python3
"""Sanitize the exact production ownership classifier without a shell harness."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
OUT=Path('/var/tmp/wsh-native-tools/doctor-evidence')
source=(ROOT/'native/doctor.c').read_text()
classifier='static int\nwsh_doctor_finding'+source.split('static int\nwsh_doctor_finding',1)[1].split('\nstatic void\nwsh_doctor_finish',1)[0]
harness='''#include <assert.h>
#include <string.h>
'''+classifier+'''
int main(void) {
    unsigned int state=90231;
    char owner[256], replaced[256];
    const char *owners[]={"wsh","external-active","external-exact","external-unknown","disabled","unset","", "wsh\\033"};
    const char *replacements[]={"0","1","unset","", "0\\n"};
    const int expected[8][5]={{0,1,-1,-1,-1},{1,-1,-1,-1,-1},{1,-1,-1,-1,-1},{2,-1,-1,-1,-1},{0,-1,-1,-1,-1},{-1,-1,-1,-1,-1},{-1,-1,-1,-1,-1},{-1,-1,-1,-1,-1}};
    for (int i=0;i<8;i++) for(int j=0;j<5;j++) assert(wsh_doctor_finding(owners[i],replacements[j])==expected[i][j]);
    for (int i=0;i<10000;i++) {
        for(int j=0;j<255;j++) {
            state=state*1664525u+1013904223u;owner[j]=(char)(1+state%255);
            state=state*1664525u+1013904223u;replaced[j]=(char)(1+state%255);
        }
        owner[255]=replaced[255]=0;
        assert(wsh_doctor_finding(owner,replaced)==-1);
    }
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='wsh-ownership-sanitizer-') as directory:
    path=Path(directory);(path/'harness.c').write_text(harness)
    command=['clang','-std=c99','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-g',str(path/'harness.c'),'-o',str(path/'harness')]
    compile_result=subprocess.run(command,capture_output=True,check=True)
    result=subprocess.run([path/'harness'],capture_output=True,check=True)
    assert not compile_result.stderr and not result.stderr
(OUT/'ownership-harness.c').write_text(harness)
(OUT/'ownership-sanitizer.json').write_text(json.dumps({'cases':40,'arbitrary_pairs':10000,'passed':True,'classifier_sha256':hashlib.sha256(classifier.encode()).hexdigest(),'command':command},indent=2)+'\n')
print('PASS: 40 ownership classifications and 10000 arbitrary byte-string pairs under ASan/UBSan with strict warnings')
