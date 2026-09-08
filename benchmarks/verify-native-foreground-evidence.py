#!/usr/bin/env python3
"""Verify native foreground argv, lifecycle, identities and readiness evidence."""
import gzip
import hashlib
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'benchmarks/native-foreground-2026-09-08'
def read(name):return json.loads((OUT/name).read_text())
def sha(data):return hashlib.sha256(data).hexdigest()
for line in (OUT/'SHA256SUMS').read_text().splitlines():
    digest,name=line.split('  ',1);assert sha((ROOT/name).read_bytes())==digest,name
build=read('build.json');meta=read('metadata.json');summary=read('summary.json');rows=read('samples.json')
assert sha(json.dumps(build['inputs'],sort_keys=True).encode())==build['build_identity']['WSH_INPUTS_SHA256']
with tarfile.open(OUT/'inputs.tar.gz') as archive:
    for name,digest in build['inputs'].items():assert sha(archive.extractfile(name).read())==digest,name
    foreground=archive.extractfile('native/foreground.c').read()
    assert sha(foreground)==read('sanitized-build.json')['foreground_c_sha256']
    parser=foreground.decode().split('\nstatic void\nwsh_foreground_run',1)[0]
    assert sha(parser.encode())==read('parser-sanitizer.json')['parser_sha256']
    original=archive.extractfile('tests/foreground-startup.zsh').read().decode()
    adapted=original.replace('${0:A:h}/fixtures/foreground-probe.c','/code/wsh/tests/fixtures/foreground-probe.c')
    adapted=adapted.replace('exec $manager run-foreground --state-root $state_root --login --','exec $bundle/bin/wsh --wsh-run --login --')
    adapted=adapted.replace('exec $manager run-foreground --state-root $state_root --','exec $bundle/bin/wsh --wsh-run --')
    adapted=adapted.replace('exec $manager -- $probe','exec $bundle/bin/wsh --wsh-run -- $probe')
    adapted=adapted.replace("  wait_for_text $'\\e]133;B' $label", "  wait_for_text $'\\e]133;P;k=i' $label\n  wait_for_text $'\\e]133;B' $label")
    assert adapted==(OUT/'foreground-native.zsh').read_text()
assert len(rows)==200 and meta['trace_mode']=='off' and meta['cpu']==0
assert meta['native_sha256']==build['binary_sha256']
for theme in ('existing','minimal'):
    selected=[row for row in rows if row['theme']==theme]
    data={variant:[row['readiness_ms'] for row in selected if row['variant']==variant] for variant in ('callback','native')}
    for pair in range(50):
        assert [row['variant'] for row in selected if row['pair']==pair]==(['callback','native'] if pair%2==0 else ['native','callback'])
    differences=sorted(data['native'][i]-data['callback'][i] for i in range(50))
    assert abs(differences[47]-summary[theme]['paired_p95_ms'])<1e-9
    assert summary[theme]['gate_ms']==3 and summary[theme]['passed'] and differences[47]<=3
    for variant in ('callback','native'):assert abs(sorted(data[variant])[24]-summary[theme][variant+'_median_ms'])<1e-9
manifest=gzip.decompress((OUT/'manifest.json.gz').read_bytes())
assert sha(manifest)==meta['manifest_sha256']
assert read('parser-sanitizer.json')['passed'] and read('parser-sanitizer.json')['arbitrary_cases']==10000
with tarfile.open(OUT/'logs.tar.gz') as archive:
    assert b'PASS: structured foreground startup preserves argv, job control' in archive.extractfile('wsh-native-foreground-test.log').read()
    assert b'PASS: sanitized native foreground' in archive.extractfile('wsh-native-foreground-sanitized-test.log').read()
for name in ('bytes-and-status.bin','bytes-and-status-sanitized.bin'):
    transcript=(OUT/name).read_bytes();assert b'ARGV:' in transcript and b'STATUS:7' in transcript
print('PASS: native foreground input identities, exact argv, PTY contracts, sanitizers and matched readiness gates')
