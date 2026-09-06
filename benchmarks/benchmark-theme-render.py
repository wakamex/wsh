#!/usr/bin/env python3
"""Measure actual renderer spans for bundled themes through the runtime protocol."""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    args.output.mkdir()
    summary = {}
    with tempfile.TemporaryDirectory(prefix='wsh-theme-render-') as tmp:
        fixture = Path(tmp)
        def git(*argv):
            subprocess.run(['git', '-C', str(fixture), *argv], check=True, stdout=subprocess.DEVNULL)
        git('init', '-q', '-b', 'main')
        git('config', 'user.name', 'Wsh theme test')
        git('config', 'user.email', 'theme@wsh.invalid')
        (fixture / 'tracked').write_text('seed\n')
        git('add', 'tracked')
        git('commit', '-qm', 'seed')
        for theme in ['minimal', 'wakamex', 'robbyrussell', 'agnoster']:
            trace = (args.output / f'{theme}.jsonl').resolve()
            env = {k: v for k, v in os.environ.items() if not k.startswith(('WSH_TRACE', 'WSH_PROFILE'))}
            env['WSH_TRACE_FILE'] = str(trace)
            process = subprocess.Popen([str(bundle / 'bin/wsh-runtime'), 'serve', '--theme', str(bundle / f'share/wsh/themes/{theme}.toml')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
            try:
                ready = json.loads(process.stdout.readline())
                assert ready['type'] == 'ready' and ready['theme'] == theme, ready
                for generation in range(1, 61):
                    (fixture / 'tracked').write_text('seed\n' if generation % 2 else 'changed\n')
                    request = dict(type='refresh', version=1, id=generation, generation=generation, cwd_hex=os.fsencode(fixture).hex(), exit_status=generation % 2, duration_ms=2300, privileged=False, reset_transient=False)
                    process.stdin.write(json.dumps(request) + '\n')
                    process.stdin.flush()
                    response = json.loads(process.stdout.readline())
                    assert response['type'] == 'snapshot' and response['generation'] == generation, response
                process.stdin.write(json.dumps(dict(type='shutdown', version=1, id=61)) + '\n')
                process.stdin.flush()
                assert json.loads(process.stdout.readline())['type'] == 'stopping'
                assert process.wait(timeout=5) == 0
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.stdin.close()
                process.stdout.close()
            spans = [json.loads(line)['render_duration_us'] for line in trace.read_text().splitlines() if json.loads(line)['event'] == 'snapshot-published']
            assert len(spans) == 60
            summary[theme] = dict(samples=60, median_us=statistics.median(spans), p90_us=sorted(spans)[53], maximum_us=max(spans))
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
