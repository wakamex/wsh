#!/usr/bin/env python3
"""Verify the retained native-entrypoint experiment without rebuilding or timing."""
import gzip,hashlib,json,math,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'benchmarks/native-entrypoint-2026-09-08'
def sha(data): return hashlib.sha256(data).hexdigest()
def read(name): return json.loads((OUT/name).read_text())
def q(values,p): return sorted(values)[math.ceil(len(values)*p)-1]
def close(a,b): assert abs(a-b)<1e-8,(a,b)
for line in (OUT/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1)
    assert sha((ROOT/name).read_bytes())==digest,name
meta=read('metadata.json');rows=read('samples.json');summary=read('summary.json')
assert len(rows)==200 and all(r['same_pid'] and 0<r['startup_ms']<8000 for r in rows)
assert meta['trace_mode']=='off' and meta['cpu']==0
assert sha(meta['config'].encode())==meta['config_sha256']
assert sha((OUT/'interactive.py').read_bytes())==meta['harness_sha256']
for mode in ['existing','minimal']:
    subset=[r for r in rows if r['mode']==mode]
    assert len(subset)==100
    data={v:[r['startup_ms'] for r in subset if r['variant']==v] for v in ['launcher','native']}
    for v,values in data.items():
        assert [r['round'] for r in subset if r['variant']==v]==list(range(50))
        assert summary[mode][v]['samples']==50
        close(q(values,.5),summary[mode][v]['median_ms']);close(q(values,.95),summary[mode][v]['p95_ms'])
    for i in range(50):
        assert [r['variant'] for r in subset if r['round']==i]==(['launcher','native'] if i%2==0 else ['native','launcher'])
    delta=[data['native'][i]-data['launcher'][i] for i in range(50)]
    d=summary[mode]['paired_delta'];close(q(delta,.5),d['median_ms']);close(q(delta,.95),d['p95_ms'])
    assert d['gate_ms']==3 and d['pass']==(q(delta,.95)<=3) and d['pass']
manifests={}
for v in ['launcher','native']:
    contents=gzip.decompress((OUT/(v+'-manifest.json.gz')).read_bytes())
    assert sha(contents)==meta['binaries'][v]['manifest.json']
    m=json.loads(contents);manifests[v]=m
    assert m['status']=='development'
    files={p['path']:p['sha256'] for p in m['files']}
    for name in ['bin/wsh','bin/zsh','bin/wsh-runtime']: assert files[name]==meta['binaries'][v][name]
    checks=read('checks-'+v+'.json')
    assert len(checks)==14 and len({r['test'] for r in checks})==14 and all(r['status']==0 for r in checks)
assert manifests['native']['zsh']['patches']==manifests['launcher']['zsh']['patches']+[sha((OUT/'native-entrypoint.patch').read_bytes())]
assert manifests['native']['zsh']['configure_args']==manifests['launcher']['zsh']['configure_args']
controls={p['path']:p['sha256'] for p in manifests['launcher']['files']}
candidates={p['path']:p['sha256'] for p in manifests['native']['files']}
assert controls['bin/wsh-runtime']==candidates['bin/wsh-runtime']
assert all(candidates[n]==s for n,s in controls.items() if n.startswith(('lib/','share/zsh/','share/wsh/defaults/','share/wsh/themes/')))
assert len(read('direct-results.json'))==12
assert len(read('pty-results.json'))==2 and all(r['status']=='pass' for r in read('pty-results.json'))
for result in read('boundary-results.json'): assert result['outputs']['native']==result['outputs']['raw']
context=next(r for r in read('direct-results.json') if 'outputs' in r)['outputs']
assert context['native']==context['raw'] and context['launcher']!=context['raw']
with tarfile.open(OUT/'logs.tar.gz','r:gz') as archive:
    logs={m.name:archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}
assert b'75 successful test scripts, 0 failures, 2 skipped' in logs['upstream-final.log']
for v in ['native','launcher']:
    log=logs['checks/'+v+'-terminal.log'].decode().splitlines()[-1].split('\t')
    assert list(map(int,log[1:]))==[10,10,10,7,6,11,10,1,9,7]
    transcript=logs['checks/'+v+'-terminal.bin']
    assert transcript.count(b'\x1b]133;A;cl=m;aid=z')==10
    assert transcript.count(b'\x1b]133;B')==10
    assert b'WSH_NO_NEWLINE\x1b]133;D' in transcript
    login=(OUT/(v+'-login.bin')).read_bytes()
    assert b'suspended' in login and b'JOB_OK:130' in login
counts=read('code-counts.json')
patch=(OUT/'native-entrypoint.patch').read_text().splitlines()
assert counts['native_c_added']==sum(line.startswith('+') and not line.startswith('+++') for line in patch)
assert counts['native_c_removed']==sum(line.startswith('-') and not line.startswith('---') for line in patch)
assert counts['native_adapter_lines']==sum(len((OUT/name).read_text().splitlines()) for name in ['native-before.zsh','native-after.zsh','native-finish.zsh'])
assert counts['control_launcher_lines']==len((OUT/'launcher.rs').read_text().splitlines())
assert counts['launcher_total']==197 and counts['native_total']==190 and counts['net_reduction']==7
assert counts['native_total']==counts['native_adapter_lines']+counts['native_c_added']-counts['native_c_removed']
with tarfile.open(OUT/'input-source.tar.gz','r:gz') as archive:
    inputs={m.name:archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}
assert sha(inputs['native-init.c'])==read('build-identities.json')['native_init_sha256']
assert counts['control_adapter_lines']==sum(len(data.splitlines()) for name,data in inputs.items() if name.startswith('integration/zdotdir.'))
for name,digest in read('build-identities.json')['prototype_inputs'].items():
    assert sha((OUT/name).read_bytes())==digest,name
assert sha(inputs['tests/profile.zsh'].replace(b'source $WSH_BUNDLE_ROOT/share/wsh/zdotdir/.zshenv',b'source $WSH_BUNDLE_ROOT/share/wsh/native-before.zsh'))==sha((OUT/'profile-native.zsh').read_bytes())
assert sha(inputs['tests/native-terminal-integration.zsh'].replace(b'[[ $remainder == *$expected* ]] && return 0',b"[[ $remainder == *$'\\e]133;P;k=i'*$expected* ]] && return 0"))==sha((OUT/'terminal.zsh').read_bytes())
with tarfile.open(OUT/'real-omz-logs.tar.gz','r:gz') as archive:
    omz_logs={m.name:archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}
omz=read('real-omz.json')
assert len(omz['results'])==4
for row in omz['results']:
    log=omz_logs[row['variant']+'-real-omz-'+row['test']+'.log']
    assert sha(log)==row['log_sha256'] and row['status']=='pass'
    assert log.splitlines()[-1].startswith(b'PASS:')
print('PASS: native entrypoint identities, startup semantics, shell contracts, upstream suite, terminal transcripts, code counts, and latency gates')
