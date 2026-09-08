#!/usr/bin/env python3
"""Exercise real native/launcher entrypoints without manager activation."""
import json,os,pathlib,shutil,subprocess,tempfile
OUT=pathlib.Path(__file__).resolve().parent
WORK=pathlib.Path('/var/tmp/wsh-native-entry-prototype')
RESULTS=[]
def record(name,**details):
    RESULTS.append(dict(test=name,**details))
    (OUT/'direct-results.json').write_text(json.dumps(RESULTS,indent=2)+'\n')
    print('PASS: '+name,flush=True)
def invoke(exe,args,env,argv0='wsh',status=0):
    p=subprocess.run([argv0]+args,executable=str(exe),env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=8)
    assert p.returncode==status,(exe,args,p.returncode,p.stdout,p.stderr)
    return p
with tempfile.TemporaryDirectory(prefix='wsh-native-direct-') as tmp:
    tmp=pathlib.Path(tmp); home=tmp/'home'; home.mkdir()
    env={k:v for k,v in os.environ.items() if not k.startswith(('WSH_','WAKTERM_','ZSH_')) and k not in ('ZDOTDIR','XDG_DATA_HOME','ENV','BASH_ENV')}
    env.update(HOME=str(home),ZDOTDIR=str(home),TERM='xterm-256color',LC_ALL='C.UTF-8',WSH_THEME='')
    for variant in ['launcher','native']:
        exe=WORK/variant/'bin/wsh'
        state=tmp/('state-'+variant);state.mkdir()
        selected=dict(env,WSH_STATE_ROOT=str(state),XDG_DATA_HOME=str(tmp/'other-data'))
        statefile=state/'bundle-state.json'
        for case,payload in [('absent',None),('corrupt',b'{broken'),('incompatible',b'{"schema_version":999}'),('unreadable',b'{"schema_version":2}')]:
            if payload is not None: statefile.write_bytes(payload)
            if case=='unreadable': statefile.chmod(0)
            p=invoke(exe,['-c','a=(one two); print -r -- "$ZSH_VERSION:${a[2]}"'],selected,argv0='-wsh')
            assert p.stdout==b'5.9.999.3-test:two\n',p
            if case=='unreadable': statefile.chmod(0o600)
            if payload is not None: assert statefile.read_bytes()==payload
        record(variant+' starts Zsh independent of user activation files',state_access='not required; chmod-zero fixture is ignored rather than read')
        arguments=[b'spaces here',b'line\nbreak',b'\xff',b'',b'$literal']
        p=invoke(exe,['-lc','printf "%s\\0" "$@"; exit 23','command-name']+arguments,env,status=23)
        assert p.stdout==b'\0'.join(arguments)+b'\0',p
        record(variant+' forwards command argv bytes and exit status')
        for flag in ['-f','--no-rcs']:
            (home/'.zshenv').write_text('print -r -- UNEXPECTED\n')
            p=invoke(exe,[flag,'-c','print -r -- OK'],env)
            assert p.stdout==b'OK\n',p
        (home/'.zshenv').unlink()
        script=tmp/'script with spaces.zsh';script.write_text('a=(one two); print -r -- "$a[2]:$1"; exit 31\n')
        assert invoke(exe,[str(script),'arg'],env,status=31).stdout==b'two:arg\n'
        record(variant+' native script invocation and no-rcs options')
        nohome=dict(env);nohome.pop('HOME');nohome.pop('ZDOTDIR')
        assert invoke(exe,['-fc','print -r -- $ZSH_VERSION'],nohome).stdout==b'5.9.999.3-test\n'
        record(variant+' no HOME under no-rcs recovery invocation')
        moved=tmp/(variant+' moved')
        shutil.copytree(WORK/variant,moved)
        # Supply no module fallback from the original install.
        (home/'.zshenv').write_text('module_path=($WSH_BUNDLE_ROOT/lib/zsh/$ZSH_VERSION); zmodload zsh/datetime; print -r -- MODULE:$EPOCHREALTIME\n')
        p=invoke(moved/'bin/wsh',['-c','print -r -- ROOT:$WSH_BUNDLE_ROOT'],env)
        assert b'MODULE:' in p.stdout and ('ROOT:'+str(moved)).encode() in p.stdout,p
        symlink=tmp/(variant+'-link');symlink.symlink_to(moved/'bin/wsh')
        assert ('ROOT:'+str(moved)).encode() in invoke(symlink,['-c','print -r -- ROOT:$WSH_BUNDLE_ROOT'],env).stdout
        (home/'.zshenv').unlink()
        record(variant+' relocated installation and symlink entrypoint')
        shutil.rmtree(moved)
    # Compare native startup context and options against the exact unmodified engine.
    redirected=tmp/'redirected';redirected.mkdir()
    (home/'.zshenv').write_text('print -r -- ENV:$ZSH_EVAL_CONTEXT; ZDOTDIR=$TEST_REDIRECT\n')
    for file,marker in [('.zprofile','PROFILE'),('.zshrc','RC'),('.zlogin','LOGIN')]:
        (redirected/file).write_text('print -r -- '+marker+':$ZSH_EVAL_CONTEXT; [[ $options[rcs] == on ]]\n')
    selected=dict(env,TEST_REDIRECT=str(redirected),WSH_DISABLE_HISTORY_SUBSTRING_SEARCH='1',WSH_DISABLE_AUTOSUGGESTIONS='1',WSH_DISABLE_SYNTAX_HIGHLIGHTING='1',WSH_DISABLE_DIRECTORY_JUMP='1')
    context={}
    for variant,exe in [('raw',WORK/'launcher/bin/zsh'),('launcher',WORK/'launcher/bin/wsh'),('native',WORK/'native/bin/wsh')]:
        p=invoke(exe,['-dlic','print -r -- DONE'],selected)
        context[variant]=p.stdout.decode().splitlines()
    assert context['native']==context['raw'],context
    assert context['launcher']!=context['raw'],context
    record('native startup restores raw Zsh evaluation context; wrapper differs',outputs=context)
    # Native startup can continue even if optional Wsh integration is absent.
    missing=tmp/'incomplete';(missing/'bin').mkdir(parents=True)
    shutil.copy2(WORK/'native/bin/wsh',missing/'bin/wsh')
    clean=dict(env,ZDOTDIR=str(tmp/'empty'))
    p=invoke(missing/'bin/wsh',['-c','print -r -- $ZSH_VERSION'],clean)
    assert p.stdout==b'5.9.999.3-test\n' and b'integration unavailable' in p.stderr,p
    record('native executable remains Zsh when optional integration is absent')
