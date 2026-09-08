#!/usr/bin/env python3
"""Compare C diagnostics with the Rust implementation on one native installation."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
WORK = Path('/var/tmp/wsh-native-tools')
BUNDLE = WORK/'installation'
NATIVE = BUNDLE/'bin/wsh'
MANAGER = ROOT/'target/release/wsh'
OUT = WORK/'doctor-evidence'


def main():
    manifest = json.loads((BUNDLE/'manifest.json').read_text())
    manifest['release_id']='development-native-doctor'
    manifest['files'] = [{'path':str(p.relative_to(BUNDLE)), 'kind':'file', 'mode':p.stat().st_mode&0o777,
                          'size':p.stat().st_size, 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                         for p in sorted(BUNDLE.rglob('*')) if p.is_file() and p.name!='manifest.json']
    (BUNDLE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    results=[]
    with tempfile.TemporaryDirectory(prefix='wsh-c-doctor-') as directory:
        base=Path(directory)
        state=base/'state'
        subprocess.run([MANAGER,'bundle','activate',BUNDLE,'--state-root',state],check=True,capture_output=True)
        defaults=BUNDLE/'share/wsh/defaults'
        exact_history=defaults/'zsh-history-substring-search.zsh'
        exact_auto=defaults/'zsh-autosuggestions.zsh'
        exact_syntax=defaults/'zsh-syntax-highlighting'
        changed_history=base/'changed-history.zsh'
        changed_auto=base/'changed-auto.zsh'
        changed_syntax=base/'changed-syntax'
        for original,changed in [(exact_history,changed_history),(exact_auto,changed_auto)]:
            changed.write_bytes(original.read_bytes()+b'\n# modified fixture\n')
        shutil.copytree(exact_syntax,changed_syntax)
        with (changed_syntax/'highlighters/main/main-highlighter.zsh').open('a') as f:f.write('\n# modified fixture\n')
        def plugins(history,auto,syntax):
            return f'source {shlex.quote(str(history))}\nsource {shlex.quote(str(auto))}\nzmodload zsh/zle\nsource {shlex.quote(str(syntax))}/zsh-syntax-highlighting.zsh\n'
        fixtures={
            'clean':'',
            'exact':plugins(exact_history,exact_auto,exact_syntax),
            'modified':plugins(changed_history,changed_auto,changed_syntax),
            'disabled':'WSH_DISABLE_HISTORY_SUBSTRING_SEARCH=1\nWSH_DISABLE_AUTOSUGGESTIONS=1\nWSH_DISABLE_SYNTAX_HIGHLIGHTING=1\n'+plugins(exact_history,exact_auto,exact_syntax),
            'omz-history':f'source {shlex.quote(str(defaults/"known-oh-my-zsh-history-substring-search.zsh"))}\n',
            'active-auto':f'source {shlex.quote(str(exact_auto))}\ntypeset -gA _ZSH_AUTOSUGGEST_BIND_COUNTS=(self-insert 1)\n',
            'noisy':'print noisy; print -u2 noisy-stderr\n',
        }
        omz=Path('/home/mihai/.oh-my-zsh')
        assert (omz/'oh-my-zsh.sh').is_file()
        omz_source=f'ZSH={shlex.quote(str(omz))}\nZSH_CACHE_DIR=$HOME/cache\nZSH_COMPDUMP=$HOME/.zcompdump\nzstyle ":omz:update" mode disabled\nplugins=(git z)\nZSH_THEME=robbyrussell\n'
        fixtures['real-omz-overlap']=omz_source+'WSH_THEME=minimal\nsource $ZSH/oh-my-zsh.sh\n'
        fixtures['real-omz-clean']=omz_source+'WSH_THEME=minimal\nif [[ -n ${WSH_THEME-} ]]; then ZSH_THEME=""; fi\nsource $ZSH/oh-my-zsh.sh\n'
        environments={}
        for name,config in fixtures.items():
            home=base/name;home.mkdir()
            (home/'.zshrc').write_text(config)
            (home/'.zshenv').write_text('unsetopt globalrcs\n')
            env={'PATH':'/usr/bin:/bin','HOME':str(home),'ZDOTDIR':str(home),'WSH_STATE_ROOT':str(state),
                 'TERM':'xterm-256color','LC_ALL':'C.UTF-8','TZ':'UTC'}
            environments[name]=env
            def invoke(native):
                return subprocess.run([NATIVE,'--wsh-doctor'] if native else [MANAGER,'doctor','--state-root',state],
                                      env=env,input=b'',capture_output=True,timeout=15)
            rust=invoke(False);c=invoke(True)
            assert rust.returncode==c.returncode==0,(name,rust,c)
            assert rust.stdout==c.stdout and not c.stderr,(name,rust,c)
            assert (home/'.zshrc').read_text()==config
            results.append({'fixture':name,'status':0,'output':c.stdout.decode(),'configuration':config})
        env=environments['clean']
        config_path=Path(env['HOME'])/'.zshrc'
        for name,config in [('early-success','exit 0\n'),('early-failure','exit 27\n'),('hung','sleep 30\n')]:
            config_path.write_text(config)
            start=time.monotonic()
            result=subprocess.run([NATIVE,'--wsh-doctor'],env=env,input=b'',capture_output=True,timeout=13)
            elapsed=time.monotonic()-start
            assert result.returncode==1 and not result.stdout,(name,result)
            assert elapsed<12 and (name!='hung' or elapsed>=9.9)
            results.append({'fixture':name,'status':result.returncode,'elapsed_seconds':elapsed,'error':result.stderr.decode()})
        config_path.write_text('sleep 30\n')
        child=subprocess.Popen([NATIVE,'--wsh-doctor'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        time.sleep(.2);child.terminate();stdout,stderr=child.communicate(timeout=2)
        assert child.returncode==143 and not stdout
        results.append({'fixture':'interrupt','status':child.returncode})
        config_path.write_text('')
        # Exercise repeated startup to expose report-close versus child-exit races.
        for _ in range(50):
            result=subprocess.run([NATIVE,'--wsh-doctor'],env=env,capture_output=True,timeout=15)
            assert result.returncode==0 and not result.stderr,result
        results.append({'fixture':'50 repeated native reports','status':0})
        affinity=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,{affinity[0]})
        samples=[]
        for pair in range(50):
            row={'pair':pair}
            for native in ([False,True] if pair%2==0 else [True,False]):
                start=time.perf_counter_ns()
                result=subprocess.run([NATIVE,'--wsh-doctor'] if native else [MANAGER,'doctor','--state-root',state],
                                      env=env,input=b'',capture_output=True,timeout=15)
                assert result.returncode==0 and not result.stderr
                row['native_ms' if native else 'rust_ms']=(time.perf_counter_ns()-start)/1e6
            samples.append(row)
        os.sched_setaffinity(0,affinity)
        p95=sorted(row['native_ms']-row['rust_ms'] for row in samples)[47]
        summary={'pairs':50,'paired_p95_ms':p95,'gate_ms':3,'passed':p95<=3,'cpu':affinity[0],
                 'native_sha256':hashlib.sha256(NATIVE.read_bytes()).hexdigest(),
                 'rust_sha256':hashlib.sha256(MANAGER.read_bytes()).hexdigest(),
                 'manifest_sha256':hashlib.sha256((BUNDLE/'manifest.json').read_bytes()).hexdigest(),
                 'omz_revision':subprocess.check_output(['git','-C',omz,'rev-parse','HEAD'],text=True).strip()}
        (OUT/'doctor-results.json').write_text(json.dumps(results,indent=2)+'\n')
        (OUT/'doctor-samples.json').write_text(json.dumps(samples,indent=2)+'\n')
        (OUT/'doctor-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary,indent=2))
        assert summary['passed'],summary


if __name__=='__main__':main()
