#!/usr/bin/env python3
"""Direct login-style job control and isolated paired startup timings."""
import gzip,hashlib,json,math,os,pathlib,pty,select,signal,subprocess,sys,tempfile,time
OUT=pathlib.Path(__file__).resolve().parent
ROOT=OUT.parents[1]
WORK=pathlib.Path('/var/tmp/wsh-native-entry-prototype')
READY=b'\x1b]133;B\x1b\\'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def wait(fd,marker,timeout=8):
    data=bytearray();end=time.monotonic()+timeout
    while marker not in data:
        assert time.monotonic()<end,bytes(data)
        if select.select([fd],[],[],.1)[0]: data.extend(os.read(fd,65536))
    return bytes(data)
def start(exe,env,home):
    started=time.monotonic_ns();pid,fd=pty.fork()
    if pid==0:
        os.chdir(home);os.sched_setaffinity(0,{0})
        os.execve(str(exe),['-wsh','-d'],env)
    return started,pid,fd
def stop(pid,fd):
    try: os.killpg(pid,signal.SIGHUP)
    except ProcessLookupError: pass
    os.close(fd);os.waitpid(pid,0)
def quant(values,p): return sorted(values)[math.ceil(len(values)*p)-1]
mode=sys.argv[1]
with tempfile.TemporaryDirectory(prefix='wsh-native-pty-') as tmp:
    home=pathlib.Path(tmp)
    config='PROMPT="PROTOTYPE> "\nZSHZ_DATA=$HOME/jump-data\n'
    (home/'.zshrc').write_text(config)
    base={k:v for k,v in os.environ.items() if not k.startswith(('WSH_','WAKTERM_','ZSH_')) and k not in ('ZDOTDIR','XDG_DATA_HOME','MODULE_PATH','BASH_ENV','ENV')}
    base.update(HOME=str(home),ZDOTDIR=str(home),TERM='xterm-256color',LC_ALL='C.UTF-8',WSH_STATE_ROOT=str(home/'no-state'))
    if mode=='correctness':
        rows=[]
        for variant in ['launcher','native']:
            env=dict(base,WSH_THEME='minimal')
            _,pid,fd=start(WORK/variant/'bin/wsh',env,home)
            transcript=bytearray()
            try:
                transcript.extend(wait(fd,READY))
                os.write(fd,b'print -r -- RUNTIME:$WSH_RUNTIME_PID:$WSH_PROMPT_OWNER\n')
                response=wait(fd,READY);transcript.extend(response)
                assert b':wsh' in response and b'RUNTIME:' in response,response
                os.write(fd,b'sleep 30\n');transcript.extend(wait(fd,b'\x1b]133;C'))
                time.sleep(.15);os.write(fd,b'\x1a')
                response=wait(fd,READY);transcript.extend(response)
                assert b'suspended' in response,response
                os.write(fd,b'fg\n');transcript.extend(wait(fd,b'\x1b]133;C'))
                time.sleep(.15);os.write(fd,b'\x03');transcript.extend(wait(fd,READY))
                os.write(fd,b'print -r -- JOB_OK:$?; exit 23\n')
                transcript.extend(wait(fd,b'JOB_OK:130'))
                _,status=os.waitpid(pid,0);assert os.waitstatus_to_exitcode(status)==23,status
                pid=None
                rows.append({'variant':variant,'status':'pass','login_argv0':True,'no_activation':True,'runtime':'local theme runtime','job_control':'Ctrl-Z, fg, Ctrl-C, prompt return, status 130, exit 23'})
            finally:
                if pid is not None: stop(pid,fd)
                else: os.close(fd)
                (OUT/(variant+'-login.bin')).write_bytes(transcript)
        (OUT/'pty-results.json').write_text(json.dumps(rows,indent=2)+'\n')
        print('PASS: both direct login entrypoints preserve runtime, job control and prompt return')
    elif mode=='measure':
        rows=[];host={'start':time.time(),'stat_before':pathlib.Path('/proc/stat').read_text(),'load_before':pathlib.Path('/proc/loadavg').read_text()}
        for theme in ['', 'minimal']:
            env=dict(base,WSH_THEME=theme)
            for index in range(50):
                for variant in (['launcher','native'] if index%2==0 else ['native','launcher']):
                    exe=WORK/variant/'bin/wsh'
                    started,pid,fd=start(exe,env,home)
                    try:
                        output=wait(fd,READY)
                        ms=(time.monotonic_ns()-started)/1e6
                        actual=os.readlink('/proc/'+str(pid)+'/exe')
                        expected=WORK/variant/'bin'/('zsh' if variant=='launcher' else 'wsh')
                        assert actual==str(expected),actual
                        rows.append({'mode':theme or 'existing','round':index,'variant':variant,'startup_ms':ms,'same_pid':True})
                    finally: stop(pid,fd)
        host.update(end=time.time(),stat_after=pathlib.Path('/proc/stat').read_text(),load_after=pathlib.Path('/proc/loadavg').read_text())
        (OUT/'host.json').write_text(json.dumps(host,indent=2)+'\n')
        (OUT/'samples.json').write_text(json.dumps(rows,indent=2)+'\n')
        summary={}
        for theme in ['existing','minimal']:
            r=[x for x in rows if x['mode']==theme]
            data={v:[x['startup_ms'] for x in r if x['variant']==v] for v in ['launcher','native']}
            deltas=[data['native'][i]-data['launcher'][i] for i in range(50)]
            summary[theme]={v:{'samples':len(a),'median_ms':quant(a,.5),'p95_ms':quant(a,.95)} for v,a in data.items()}
            summary[theme]['paired_delta']={'median_ms':quant(deltas,.5),'p95_ms':quant(deltas,.95),'gate_ms':3,'pass':quant(deltas,.95)<=3}
        (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        metadata={'source_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),'command':'python3 benchmarks/native-entrypoint-2026-09-08/interactive.py measure','cpu':0,'trace_mode':'off','config':config,'config_sha256':hashlib.sha256(config.encode()).hexdigest(),'host':subprocess.check_output(['uname','-a']).decode().strip(),'enabled_components':'directory jumping, history substring search, autosuggestions, syntax highlighting; existing prompt or minimal theme with local Rust runtime','artifacts':'unsigned local development prototypes','zsh_source_lock':json.loads((ROOT/'build/zsh-sources/zsh-cad0d67c.json').read_text()),'binaries':{v:{str(p.relative_to(WORK/v)):sha(p) for p in [WORK/v/'bin/wsh',WORK/v/'bin/zsh',WORK/v/'bin/wsh-runtime',WORK/v/'manifest.json']} for v in ['launcher','native']},'harness_sha256':sha(pathlib.Path(__file__))}
        (OUT/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
        print(json.dumps(summary,indent=2))
    else: raise ValueError(mode)
