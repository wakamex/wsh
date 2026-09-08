#!/usr/bin/env python3
"""Compare startup semantics with raw Zsh, including isolated real global files."""
import json,os,pathlib,subprocess,tempfile
OUT=pathlib.Path(__file__).resolve().parent
WORK=pathlib.Path('/var/tmp/wsh-native-entry-prototype')
rows=[]
with tempfile.TemporaryDirectory(prefix='wsh-native-boundaries-') as tmp:
    tmp=pathlib.Path(tmp);home=tmp/'home';home.mkdir();etc=tmp/'etc';etc.mkdir()
    env={'PATH':'/usr/bin:/bin','HOME':str(home),'ZDOTDIR':str(home),'TERM':'dumb','LC_ALL':'C.UTF-8'}
    executables={'raw':WORK/'launcher/bin/zsh','launcher':WORK/'launcher/bin/wsh','native':WORK/'native/bin/wsh'}
    for rc in [None,'true','false']:
        if rc is not None: (home/'.zshenv').write_text(rc+'\n')
        for theme in [None,'']:
            selected=dict(env)
            if theme is not None: selected['WSH_THEME']=theme
            outputs={}
            for name,exe in executables.items():
                p=subprocess.run([str(exe),'-c','print -r -- STATUS:$?'],env=selected,capture_output=True,timeout=5)
                assert p.returncode==0,p
                outputs[name]=p.stdout.decode().strip()
            assert outputs['raw']==outputs['native'],outputs
            rows.append({'case':'last startup status','zshenv':rc,'theme':theme,'outputs':outputs})
    (home/'.zshenv').unlink()
    # bwrap supplies real global files in a private mount namespace, without host mutation.
    for file in ['zshenv','zprofile','zshrc','zlogin','zlogout']:
        (etc/file).write_text('print -r -- GLOBAL-'+file+':$options[rcs]:$options[globalrcs]\n')
        (home/('.'+file)).write_text('print -r -- USER-'+file+':$options[rcs]:$options[globalrcs]\n')
    for case,flags,extra in [('ordinary',['-lic'],''),('no-global',['-dlic'],''),('user-disables-rcs',['-lic'],'unsetopt rcs\n'),('user-disables-global',['-lic'],'unsetopt globalrcs\n')]:
        (home/'.zshenv').write_text('print -r -- USER-zshenv:$options[rcs]:$options[globalrcs]\n'+extra)
        outputs={}
        for name,exe in executables.items():
            args=['bwrap','--ro-bind','/','/','--unshare-user','--unshare-pid','--proc','/proc','--ro-bind',str(etc),'/etc','--',str(exe)]+flags+['print -r -- DONE:$options[rcs]:$options[globalrcs]']
            p=subprocess.run(args,env=env,capture_output=True,timeout=8)
            assert p.returncode==0,(name,case,p.stdout,p.stderr)
            outputs[name]=[l for l in p.stdout.decode().splitlines() if l.startswith(('GLOBAL-','USER-','DONE:'))]
        assert outputs['native']==outputs['raw'],(case,outputs)
        rows.append({'case':case,'outputs':outputs})
(OUT/'boundary-results.json').write_text(json.dumps(rows,indent=2)+'\n')
print('PASS: native startup preserves raw Zsh status, global/user file order, RCS and GLOBAL_RCS')
