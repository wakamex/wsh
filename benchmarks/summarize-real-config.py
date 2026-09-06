#!/usr/bin/env python3
"""Regenerate timing summaries from retained real-configuration samples."""
import csv
import math
from pathlib import Path
import statistics
import sys


def percentile(values):
    return sorted(values)[math.ceil(len(values) * .9) - 1]


def summarize(directory):
    rows = list(csv.DictReader((directory / 'timing.tsv').open(), delimiter='\t'))
    samples = {}
    paired = {}
    for row in rows:
        if row['block'] == 'warmup':
            continue
        value = float(row['first_editable_ms'])
        samples.setdefault((row['config'], row['variant']), []).append(value)
        paired.setdefault((row['config'], row['block'], row['repetition']), {})[row['variant']] = value
    with (directory / 'summary.tsv').open('w') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(['config', 'variant', 'samples', 'median_ms', 'p90_ms', 'maximum_ms'])
        for (config, variant), values in samples.items():
            writer.writerow([config, variant, len(values), f'{statistics.median(values):.6f}', f'{percentile(values):.6f}', f'{max(values):.6f}'])
    overhead = {}
    for (config, _, _), pair in paired.items():
        assert set(pair) == {'direct', 'normal', 'profile'}, pair
        overhead.setdefault(config, []).append(pair['profile'] - pair['normal'])
    empty_increment = percentile(samples['empty', 'normal']) - percentile(samples['empty', 'direct'])
    with (directory / 'gates.tsv').open('w') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(['config', 'wsh_minus_direct_p90_ms', 'excess_over_empty_increment_ms', 'followup_threshold_ms', 'startup_followup', 'paired_profile_median_ms', 'paired_profile_p90_ms', 'profile_3ms_gate'])
        for config, values in overhead.items():
            direct = percentile(samples[config, 'direct'])
            delta = percentile(samples[config, 'normal']) - direct
            excess = delta - empty_increment
            limit = max(5, direct * .1)
            p90 = percentile(values)
            writer.writerow([config, f'{delta:.6f}', f'{excess:.6f}', f'{limit:.6f}', 'investigate' if excess > limit else 'pass', f'{statistics.median(values):.6f}', f'{p90:.6f}', 'pass' if p90 <= 3 else 'fail'])

    if (directory / 'control.tsv').exists():
        pairs = {}
        for row in csv.DictReader((directory / 'control.tsv').open(), delimiter='\t'):
            pairs.setdefault((row['config'], row['repetition']), {})[row['block']] = float(row['first_editable_ms'])
        controls = {}
        for (config, _), pair in pairs.items():
            controls.setdefault(config, []).append(pair['b'] - pair['a'])
        with (directory / 'control-summary.tsv').open('w') as stream:
            writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
            writer.writerow(['config', 'pairs', 'median_b_minus_a_ms', 'p90_b_minus_a_ms', 'maximum_absolute_difference_ms'])
            for config, values in controls.items():
                writer.writerow([config, len(values), round(statistics.median(values), 6), round(percentile(values), 6), round(max(map(abs, values)), 6)])


if __name__ == '__main__':
    summarize(Path(sys.argv[1]))
