#!/usr/bin/env python3
"""Export numeric profile spans and argument-free executable events from private runs."""
import collections
import csv
import json
import gzip
import io
import tarfile
from pathlib import Path
import re
import statistics
import sys

work, output = map(Path, sys.argv[1:3])
spans = []
archive_buffer = io.BytesIO()
archive = tarfile.open(fileobj=archive_buffer, mode="w")
for terminal in sorted(work.glob('timing-*-profile-*.terminal')):
    label = terminal.stem
    config, rest = label[len('timing-'):].split('-profile-', 1)
    if rest.startswith('warmup-'):
        continue
    text = terminal.read_text(errors='replace')
    report = text[text.rfind('Wsh profile\n'):]
    match = re.search(r'^Trace: (.+)$', report, re.M)
    if not match:
        raise SystemExit(f'missing profile report: {label}')
    profile = Path(match[1].strip())
    # Default traces are schema-validated by the production reporter on normal exit.
    # Retain their exact bytes without the private metadata path or terminal transcript.
    payload = (profile / 'trace.jsonl').read_bytes()
    member = tarfile.TarInfo(f'{label}.jsonl')
    member.size = len(payload)
    member.mode = 0o600
    archive.addfile(member, io.BytesIO(payload))
    for field, value in re.findall(r'^([^\n:]+): ([0-9.]+) ms$', report, re.M):
        spans.append((config, rest, field, float(value)))
archive.close()
(output / 'profile-traces.tar.gz').write_bytes(gzip.compress(archive_buffer.getvalue(), mtime=0))
with (output / 'spans.tsv').open('w') as stream:
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerow(['config', 'sample', 'span_or_milestone', 'milliseconds'])
    writer.writerows(spans)
groups = collections.defaultdict(list)
for config, _, field, value in spans:
    groups[config, field].append(value)
with (output / 'span-summary.tsv').open('w') as stream:
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerow(['config', 'span_or_milestone', 'samples', 'median_ms'])
    for (config, field), values in groups.items():
        writer.writerow([config, field, len(values), f'{statistics.median(values):.3f}'])

rows = list(csv.DictReader((output / 'diagnostics.tsv').open(), delimiter='\t'))
events = []
for row in rows:
    config, variant = row['config'], row['variant']
    label = f'diagnostics-{config}-{variant}-{row["block"]}-0'
    if row['block'] == 'functions':
        text = (work / f'{label}.terminal').read_text(errors='replace')
        report = text[text.rfind('Wsh profile\n'):]
        report = re.sub(r'^Trace: .*$', 'Trace: retained privately; default-profile traces are in profile-traces.tar.gz', report, flags=re.M)
        (output / f'{config}-functions.txt').write_text(report.strip() + '\n')
        continue
    interval = json.loads(row['state_or_detail'])
    pending = {}
    for line in (work / f'{label}.strace').read_text().splitlines():
        prefix = re.match(r'(\d+)\s+([0-9.]+)\s+(.*)', line)
        if not prefix:
            continue
        pid, timestamp, syscall = prefix.groups()
        timestamp = float(timestamp)
        match = re.match(r'execve\("([^"\n]+)"', syscall)
        if match:
            pending[pid] = (timestamp, Path(match[1]).name)
        if (match or syscall.startswith('<... execve resumed>')) and re.search(r'= 0$', syscall):
            started, executable = pending.pop(pid)
            if started <= interval['transition_end']:
                phase = 'startup' if started < interval['transition_start'] else 'noop-transition'
                events.append((config, variant, phase, pid, f'{started:.6f}', executable))
with (output / 'process-events.tsv').open('w') as stream:
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerow(['config', 'variant', 'phase', 'pid', 'unix_seconds', 'executable_basename'])
    writer.writerows(events)
counts = collections.Counter((config, variant, phase, executable) for config, variant, phase, _, _, executable in events)
with (output / 'process-counts.tsv').open('w') as stream:
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerow(['config', 'variant', 'phase', 'executable_basename', 'count'])
    for key, count in sorted(counts.items()):
        writer.writerow([*key, count])
