#!/usr/bin/env python3
"""Run existing component contracts through native invocation, not a manager shim."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=Path(sys.argv[1]).resolve()
OUT=Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True,exist_ok=True)
ZSH=ROOT/'build/out/zsh-cad0d67c-wsh2/bin/zsh'
MANAGER=ROOT/'target/release/wsh'
results=[]
for name in ('history-substring-search','autosuggestions','syntax-highlighting','plugin-doctor','directory-jump','named-themes','zsh-config-coexistence','prompt-ownership','foreground-startup'):
    source=(ROOT/'tests'/(name+'.zsh')).read_text()
    source=re.sub(r'\$manager bundle activate \$bundle --state-root \$[^\s]+', '$manager bundle verify $bundle',source)
    source=re.sub(r'\$manager run --state-root \$[^\s]+ -- ', '$bundle/bin/wsh -d ',source)
    source=re.sub(r'\$manager run --state-root \$[^\s]+', '$bundle/bin/wsh -d',source)
    source=re.sub(r'\$manager doctor --state-root \$[^\s)]+', '$bundle/bin/wsh --wsh-doctor',source)
    source=source.replace('${0:A:h}/fixtures/foreground-probe.c',str(ROOT/'tests/fixtures/foreground-probe.c'))
    if name=='zsh-config-coexistence':
        source=source.replace('WSH_CONFIG_STATE:${redirected_zdotdir}:${redirected_zdotdir}:1:off:on:2:2:',
                              'WSH_CONFIG_STATE:${redirected_zdotdir}:unset:1:off:on:2:2:')
        source=source.replace('user ZDOTDIR was not restored', 'native ZDOTDIR or removed launcher metadata is incorrect')
    if name=='prompt-ownership':
        source=source.replace('exec $manager profile --state-root $state', 'exec $bundle/bin/wsh --wsh-profile -- -d')
        source=source.replace('$manager profile report ', '$bundle/bin/wsh --wsh-profile-report ')
        source=source.replace('export WSH_TEST_ZSH=$bundle/bin/zsh', 'export WSH_TEST_ZSH=/var/tmp/wsh-native-entry-prototype/launcher/bin/zsh')
        source=source.replace('exec $bundle/bin/zsh -di ${=login_flag}', 'exec $WSH_TEST_ZSH -di ${=login_flag}')
    if name=='foreground-startup':
        source=source.replace('exec $manager run-foreground --state-root $state_root --login --', 'exec $bundle/bin/wsh --wsh-run --login --')
        source=source.replace('exec $manager run-foreground --state-root $state_root --', 'exec $bundle/bin/wsh --wsh-run --')
        source=source.replace('exec $manager -- $probe', 'exec $bundle/bin/wsh --wsh-run -- $probe')
        source=source.replace("  wait_for_text $'\\e]133;B' $label", "  wait_for_text $'\\e]133;P;k=i' $label\n  wait_for_text $'\\e]133;B' $label")
    test=OUT/(name+'.zsh');test.write_text(source)
    command=[ZSH,test,MANAGER,BUNDLE]
    if name=='zsh-config-coexistence':command.append('present')
    if name=='foreground-startup':command.append('candidate')
    if name in ('directory-jump','prompt-ownership'):command.append('/home/mihai/.oh-my-zsh')
    with (OUT/(name+'.log')).open('wb') as log:
        result=subprocess.run([str(value) for value in command],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180,
                              env=dict(os.environ,WSH_EXPECT_NATIVE_TERMINAL_PASS='1'))
    results.append({'test':name,'command':[str(value) for value in command],'status':result.returncode})
    (OUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(name,result.returncode,flush=True)
if any(row['status'] for row in results):raise SystemExit(1)
