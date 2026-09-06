#!/usr/bin/env python3
"""Probe actual ZLE buffer, suggestion and highlights using fixed synthetic input."""
import csv
import importlib.util
from pathlib import Path
import re
import sys

spec = importlib.util.spec_from_file_location('matrix', Path(__file__).with_name('benchmark-real-config.py'))
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)
output, work, bundle = [Path(x).resolve() for x in sys.argv[1:4]]
probe = r'''_wsh_matrix_probe() { print -nr -- $'\x1eEDIT_STATE:'${BUFFER}:$POSTDISPLAY:${#region_highlight}:$'\x1f'; }; zle -N _wsh_matrix_probe; bindkey '^X^G' _wsh_matrix_probe; bindkey '^X^H' history-substring-search-up'''


def inspect(shell):
    offset = shell.send(b'\x18\x07')
    data = shell.read_until(b'\x1f', offset)
    match = re.search(rb'\x1eEDIT_STATE:(.*?):(.*?):(\d+):\x1f', data)
    if not match:
        raise RuntimeError('missing editor probe state')
    return match.groups()


with (output / 'editing.tsv').open('w') as stream:
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerow(['config', 'variant', 'substring_history', 'autosuggestion', 'highlight_regions', 'result'])
    for config in matrix.CONFIGS:
        variants = ['direct', 'normal'] if config in ['plugins', 'wakamex-plugins', 'actual'] else ['normal']
        for variant in variants:
            shell = matrix.Shell(work, bundle, matrix.ROOT / 'target/release/wsh', config, variant, f'editing-{config}-{variant}')
            try:
                shell.command(probe)
                shell.command('print -r -- WSH_MATRIX_HISTORY_SEED')
                shell.send('print -r -- WSH_MATRIX_HISTORY_')
                shell.settle(0.15)
                buffer, suggestion, highlights = inspect(shell)
                suggestion_ok = suggestion == b'SEED'
                highlighting_ok = int(highlights) > 0
                offset = shell.send(b'\x03')
                shell.read_until(matrix.READY, offset)
                shell.send('WSH_MATRIX_HISTORY_')
                shell.settle(0.05)
                shell.send(b'\x18\x08')
                shell.settle(0.05)
                buffer, _, _ = inspect(shell)
                history_ok = buffer == b'print -r -- WSH_MATRIX_HISTORY_SEED'
                offset = shell.send(b'\x03')
                shell.read_until(matrix.READY, offset)
                result = 'pass' if suggestion_ok and highlighting_ok and history_ok else 'fail'
                writer.writerow([config, variant, history_ok, suggestion_ok, int(highlights), result])
                stream.flush()
                print(config, variant, result, flush=True)
            finally:
                shell.close()
