#!/usr/bin/env python3
"""Compare byte-identical controls to assess the paired-overhead noise floor."""
import importlib.util
import json
from pathlib import Path
import time

SOURCE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('component_experiment', SOURCE / 'run.py')
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)
OUT = experiment.OUT

def main():
    rows = []
    host = {'before': Path('/proc/stat').read_text(), 'load_before': Path('/proc/loadavg').read_text(), 'started': time.time()}
    metadata = json.loads((OUT / 'metadata.json').read_text())
    assert experiment.sha(SOURCE / 'run.py') == metadata['harness_sha256']
    identities = {'variance_harness_sha256': experiment.sha(SOURCE / 'variance.py'),
                  'variance_plan_sha256': experiment.sha(SOURCE / 'variance-plan.md'),
                  'control_prototype_sha256': metadata['control_prototype_sha256']}
    (OUT / 'variance-metadata.json').write_text(json.dumps(identities, indent=2) + '\n')
    for cache in ('cold', 'warm'):
        home = OUT / 'work' / ('deferred-control-' + cache)
        assert experiment.sha(home / 'deferred.zsh') == identities['control_prototype_sha256']
    try:
        for index in range(50):
            caches = ['cold', 'warm'] if index % 2 == 0 else ['warm', 'cold']
            labels = ['a', 'b'] if index % 2 == 0 else ['b', 'a']
            for cache in caches:
                variant = 'deferred-control-' + cache
                for label in labels:
                    if cache == 'cold':
                        (OUT / 'work' / variant / '.zcompdump').unlink(missing_ok=True)
                    row = experiment.observe(variant, 'variance-' + str(index) + '-' + cache + '-' + label)
                    row.update(round=index, cache=cache, label=label)
                    rows.append(row)
            if index % 10 == 9:
                print('Completed variance rounds:', index + 1, flush=True)
    finally:
        (OUT / 'variance-samples.json').write_text(json.dumps(rows, indent=2) + '\n')
        host.update(after=Path('/proc/stat').read_text(), load_after=Path('/proc/loadavg').read_text(), ended=time.time())
        (OUT / 'variance-host.json').write_text(json.dumps(host, indent=2) + '\n')
    summary = {}
    for cache in ('cold', 'warm'):
        group = [r for r in rows if r['cache'] == cache]
        pairs = [{r['label']: r for r in group if r['round'] == i} for i in range(50)]
        delta = [p['b']['first_tab_ms'] - p['a']['first_tab_ms'] for p in pairs]
        summary[cache] = {'pairs': len(pairs), 'paired_difference_median_ms': experiment.percentile(delta, 50),
                          'paired_difference_p95_ms': experiment.percentile(delta, 95),
                          'exceeds_3_ms_without_clocks': experiment.percentile(delta, 95) > 3}
    (OUT / 'variance-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)

if __name__ == '__main__':
    main()
