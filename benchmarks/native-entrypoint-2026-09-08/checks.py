#!/usr/bin/env python3
"""Run existing shell contracts through the unchanged manager and each prototype bundle."""
import json,os,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=pathlib.Path(__file__).resolve().parent
WORK=pathlib.Path('/var/tmp/wsh-native-entry-prototype')
ZSH=ROOT/'build/out/zsh-cad0d67c-wsh2/bin/zsh'
MANAGER=ROOT/'target/release/wsh'
results=[]
for variant in sys.argv[1:] or ['launcher','native']:
    bundle=WORK/variant
    commands=[]
    for name in ['history-substring-search','autosuggestions','syntax-highlighting','plugin-doctor','prompt-ownership','directory-jump','named-themes','profile','profile-readiness']:
        test = OUT/'profile-native.zsh' if variant=='native' and name=='profile' else ROOT/'tests'/(name+'.zsh')
        commands.append((name,[ZSH,test,MANAGER,bundle]))
    commands.append(('config',[ZSH,ROOT/'tests/zsh-config-coexistence.zsh',MANAGER,bundle,'present']))
    commands.append(('foreground',[ZSH,ROOT/'tests/foreground-startup.zsh',MANAGER,bundle,'candidate']))
    commands.append(('early-terminal',[sys.executable,ROOT/'tests/early-terminal-policy.py',MANAGER,bundle]))
    commands.append(('login-manager',[sys.executable,ROOT/'tests/login-shell.py',MANAGER,bundle]))
    commands.append(('terminal',[ZSH,OUT/'terminal.zsh',bundle/'bin/zsh','/dev/null','native',WORK/'checks'/(variant+'-terminal.bin')]))
    for name,args in commands:
        log=WORK/'checks'/(variant+'-'+name+'.log')
        try:
            with log.open('wb') as f:
                p=subprocess.run([str(a) for a in args],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=150,env=dict(os.environ,WSH_EXPECT_NATIVE_TERMINAL_PASS="1"))
            status=p.returncode
        except subprocess.TimeoutExpired: status='timeout'
        results.append({'variant':variant,'test':name,'status':status,'command':[str(a) for a in args]})
        (OUT/('checks-'+variant+'.json')).write_text(json.dumps([r for r in results if r['variant']==variant],indent=2)+'\n')
        print(variant,name,status,flush=True)
if any(row['status'] != 0 for row in results):
    raise SystemExit(1)
