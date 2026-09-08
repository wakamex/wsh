#!/usr/bin/env python3
"""Compare native startup with the same upstream engine and exercise relocation."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BUNDLE=Path(sys.argv[1]).resolve()
OUT=Path(sys.argv[2]).resolve();OUT.mkdir(parents=True,exist_ok=True)
NATIVE=BUNDLE/'bin/wsh'
RAW=Path('/var/tmp/wsh-native-entry-prototype/launcher/bin/zsh')
results=[]

def run(binary,arguments,env,expected=0,argv0=None):
    result=subprocess.run([argv0 or str(binary),*arguments],executable=binary,env=env,input=b'',capture_output=True,timeout=10)
    assert result.returncode==expected,(binary,arguments,result)
    return result

with tempfile.TemporaryDirectory(prefix='wsh-native-startup-') as directory:
    root=Path(directory);home=root/'home';home.mkdir();redirect=root/'redirect';redirect.mkdir()
    env={'PATH':'/usr/bin:/bin','HOME':str(home),'ZDOTDIR':str(home),'TERM':'xterm-256color','LC_ALL':'C.UTF-8','WSH_THEME':''}
    env.update({key:os.environ[key] for key in ('ASAN_OPTIONS','UBSAN_OPTIONS') if key in os.environ})
    (home/'.zshenv').write_text('unsetopt globalrcs\n')
    for name,payload in [('missing',None),('corrupt',b'{broken'),('incompatible',b'{"schema_version":999}'),('unreadable',b'{"schema_version":2}')]:
        state=root/name;state.mkdir()
        if payload is not None:(state/'bundle-state.json').write_bytes(payload)
        if name=='unreadable':state.chmod(0)
        selected=dict(env,WSH_STATE_ROOT=str(state),XDG_DATA_HOME=str(root/'unused'))
        output=run(NATIVE,['-lc','a=(one two); print -r -- "$a[2]"'],selected,argv0='-wsh')
        assert output.stdout==b'two\n',output
        if name=='unreadable':state.chmod(0o700)
        if payload is not None:assert (state/'bundle-state.json').read_bytes()==payload
        results.append({'case':name+' activation state','status':0})
    values=[b'',b'\xff',b'space value',b'line\nbreak',b'$(false)']
    output=run(NATIVE,['-lc','printf "%s\\0" "$@"; exit 23','zero',*values],env,23)
    assert output.stdout==b'\0'.join(values)+b'\0'
    results.append({'case':'native command argv bytes and status','status':23})
    script=root/'script with spaces';script.write_text('print -r -- "$1"; exit 31\n')
    assert run(NATIVE,['--',str(script),'argument'],env,31).stdout==b'argument\n'
    results.append({'case':'native script delimiter and status','status':31})
    for statement in ('', 'true\n', 'false\n'):
        (home/'.zshenv').write_text(statement)
        outputs=[run(binary,['-dc','print -r -- STATUS:$?'],env).stdout for binary in (RAW,NATIVE)]
        assert outputs[0]==outputs[1],outputs
        results.append({'case':'initial status','zshenv':statement,'output':outputs[1].decode()})
    (home/'.zshenv').write_text('print -r -- ENV:$ZSH_EVAL_CONTEXT; ZDOTDIR=$REDIRECT\n')
    for name in ('zprofile','zshrc','zlogin','zlogout'):
        (redirect/('.'+name)).write_text('print -r -- '+name+':$ZSH_EVAL_CONTEXT\n')
    selected=dict(env,REDIRECT=str(redirect))
    outputs=[run(binary,['-dlic','print -r -- DONE'],selected).stdout for binary in (RAW,NATIVE)]
    assert outputs[0]==outputs[1],outputs
    results.append({'case':'redirected user files, native context and login/logout order','output':outputs[1].decode()})
    (home/'.zshenv').write_text('print UNEXPECTED\n')
    for option in ('-f','--no-rcs'):
        output=run(NATIVE,[option,'-c','print -r -- OK'],env)
        assert output.stdout==b'OK\n'
    nohome={k:v for k,v in env.items() if k not in ('HOME','ZDOTDIR')}
    assert run(NATIVE,['-fc','print -r -- $ZSH_VERSION'],nohome).stdout==b'5.9.999.3-test\n'
    results.append({'case':'no-rcs and missing HOME recovery','status':0})
    (home/'.zshenv').write_text('unsetopt globalrcs\n')
    (home/'.zlogin').write_text('export WSH_THEME=minimal\n')
    output=run(NATIVE,['-lc',"/usr/bin/env | /usr/bin/grep '^WSH_THEME='"],env,1)
    assert not output.stdout
    (home/'.zlogin').unlink()
    results.append({'case':'login export of theme does not enter child environment','status':0})
    moved=root/'relocated \udcff installation';shutil.copytree(BUNDLE,moved)
    for flags in (['-f','-c'],['-c']):
        (home/'.zshenv').write_text('unsetopt globalrcs\nmodule_path=($module_path[1]); zmodload zsh/datetime\n')
        output=run(moved/'bin/wsh',[*flags,'module_path=($module_path[1]); zmodload zsh/datetime; print -r -- MODULE:$module_path[1]'],env)
        assert output.stdout==b'MODULE:'+os.fsencode(moved)+b'/lib/zsh/5.9.999.3-test\n',output
    link=root/'wsh-link';link.symlink_to(moved/'bin/wsh')
    output=run(link,['-c','print -r -- ROOT:$WSH_BUNDLE_ROOT'],env)
    assert output.stdout==b'ROOT:'+os.fsencode(moved)+b'\n',output
    results.append({'case':'non-UTF-8 relocation, early module load, no-rcs module load and symlink resolution','status':0})
    only=root/'only';(only/'bin').mkdir(parents=True);shutil.copy2(NATIVE,only/'bin/wsh')
    selected=dict(env,ZDOTDIR=str(root/'empty'))
    output=run(only/'bin/wsh',['-c','print -r -- $ZSH_VERSION'],selected)
    assert output.stdout==b'5.9.999.3-test\n' and b'integration unavailable' in output.stderr
    results.append({'case':'missing optional integration preserves basic Zsh','status':0})
    # Real global startup and option boundaries in a private mount namespace.
    etc=root/'etc';etc.mkdir()
    for name in ('zshenv','zprofile','zshrc','zlogin','zlogout'):
        (etc/name).write_text('print -r -- GLOBAL-'+name+':$options[rcs]:$options[globalrcs]\n')
        (home/('.'+name)).write_text('print -r -- USER-'+name+':$options[rcs]:$options[globalrcs]\n')
    for case,flags,extra in [('ordinary',['-lic'],''),('no-global',['-dlic'],''),('user-disables-rcs',['-lic'],'unsetopt rcs\n'),('user-disables-global',['-lic'],'unsetopt globalrcs\n')]:
        (home/'.zshenv').write_text('print -r -- USER-zshenv:$options[rcs]:$options[globalrcs]\n'+extra)
        outputs=[]
        for binary in (RAW,NATIVE):
            command=['bwrap','--unshare-user','--unshare-pid','--ro-bind','/','/','--dev-bind','/dev','/dev','--proc','/proc','--ro-bind',str(etc),'/etc','--',str(binary),*flags,'print -r -- DONE:$options[rcs]:$options[globalrcs]']
            result=subprocess.run(command,env=env,input=b'',capture_output=True,timeout=10)
            assert result.returncode==0,result
            outputs.append([line for line in result.stdout.decode().splitlines() if line.startswith(('GLOBAL-','USER-','DONE:'))])
        assert outputs[0]==outputs[1],(case,outputs)
        results.append({'case':case,'output':outputs[1]})
(OUT/'startup-results.json').write_text(json.dumps(results,indent=2)+'\n')
print('PASS:',len(results),'native startup, state, context, status, relocation, module and global-file cases')
