import ast
import hashlib
import json
import os
import pathlib
import select
import sys
import tempfile
import time

baseline, candidate, output = map(pathlib.Path, sys.argv[1:4])
output.mkdir(parents=True, exist_ok=True)
source = pathlib.Path(__file__).resolve().parents[2] / 'tests/history-persistence.py'
tree = ast.parse(source.read_text())
tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef))]
ns = {'OUT': output}
exec(compile(tree, str(source), 'exec'), ns)
rows = []
with tempfile.TemporaryDirectory(prefix='wsh-history-timing-') as temporary:
    for pair in range(30):
        for label, binary in ([('before', baseline), ('after', candidate)] if pair % 2 == 0 else [('after', candidate), ('before', baseline)]):
            home = pathlib.Path(temporary) / f'{pair}-{label}'
            home.mkdir()
            ns['BINARY'] = binary.resolve()
            start = time.perf_counter_ns()
            shell = ns['Shell'](home, f'{pair}-{label}')
            startup = (time.perf_counter_ns() - start) / 1e6
            try:
                # Measure Enter-to-prompt after editing/redraw has settled.
                os.write(shell.fd, b': WSH_HISTORY_TIMING')
                deadline = time.monotonic() + 5
                while select.select([shell.fd], [], [], .05)[0]:
                    assert time.monotonic() < deadline, 'editing did not settle'
                    shell.output.extend(os.read(shell.fd, 65536))
                start = time.perf_counter_ns()
                os.write(shell.fd, b'\n')
                shell.ready()
                command = (time.perf_counter_ns() - start) / 1e6
                shell.close()
            finally:
                shell.close(kill=True)
            rows.append({'pair': pair, 'variant': label, 'startup_ms': startup, 'command_ms': command})

def p90(values):
    return sorted(values)[int((len(values) - 1) * .9 + .999999)]
summary = {}
for metric, limit in [('startup_ms', 3), ('command_ms', 1)]:
    before = {r['pair']: r[metric] for r in rows if r['variant'] == 'before'}
    after = {r['pair']: r[metric] for r in rows if r['variant'] == 'after'}
    delta = [after[i] - before[i] for i in before]
    summary[metric] = {'before_p90': p90(list(before.values())), 'after_p90': p90(list(after.values())), 'paired_p90_overhead': p90(delta), 'limit': limit, 'passed': p90(delta) <= limit}
result = {'samples': rows, 'summary': summary, 'command_boundary': 'Enter to OSC 133 B after 50 ms terminal-output quiet', 'binaries': {k: {'path': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for k, p in [('before', baseline), ('after', candidate)]}, 'harness_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
(output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(summary, indent=2))
assert all(s['passed'] for s in summary.values())
