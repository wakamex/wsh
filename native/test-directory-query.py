#!/usr/bin/env python3
"""Compare the private query kernel with the actual pinned Zsh-z implementation."""
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys

binary, module, prototype, output = map(Path, sys.argv[1:])
output.mkdir(parents=True, exist_ok=True)
home = output / "home"
home.mkdir(exist_ok=True)
names = ["project", "Project", "project space", "project[1]", "project$(false)",
         "project`false`", "project;false", "project\\x", "projecté", "PROJECT",
         "project/new", "other", "project%F", "project'quote", "project\ttab"]
entries = []
for i, name in enumerate(names):
    path = home / name
    path.mkdir(parents=True, exist_ok=True)
    entries.append(f"{path}|{i % 5 + 1}.5|{1700000000 + i * 1000}\n")
entries += [f"{home}/missing/project|99|1700000000\n", "malformed\n"]
(home / "db").write_text("".join(entries))
original_data = (home / "db").read_bytes()
script = output / "compare.zsh"
script.write_text('''module_path=($1 $module_path)
zmodload wshdirectory || exit 2
source $2
shift 2
ZSHZ_CASE=$1 ZSHZ_TRAILING_SLASH=$2 ZSHZ_UNCOMMON=$3
[[ $4 == keep ]] && ZSHZ_KEEP_DIRS=($HOME/missing)
shift 4
zshz "$@"
result=$?
print -r -- "WSH_RESULT:$result"
''')
cases = []
for mode, trail, uncommon, keep, method, query in itertools.product(
        ["", "ignore", "smart"], ["0", "1"], ["0", "1"], ["none", "keep"],
        [[], ["-r"], ["-t"], ["-l"], ["--complete"]],
        ["project", "Project", "space", "[pP]roject", "project*", "absent"]):
    args = [mode, trail, uncommon, keep, "-e", *method, query]
    results = []
    for owner in ("control", "candidate"):
        env = dict(PATH="/usr/bin:/bin", HOME=str(home), ZSHZ_DATA=str(home / "db"),
                   WSH_QUERY_NOW="1800000000", LC_ALL="C.UTF-8")
        env.update({k: v for k, v in os.environ.items() if k.endswith("SAN_OPTIONS")})
        run = subprocess.run([binary, "-df", script, module, prototype / f"{owner}.zsh", *args],
                             env=env, capture_output=True, timeout=5)
        results.append(dict(status=run.returncode, stdout=run.stdout.hex(), stderr=run.stderr.hex()))
        assert run.returncode == 0 and not run.stderr, results[-1]
    cases.append(dict(args=args, results=results, equal=results[0] == results[1]))
    if results[0] != results[1]:
        break
(output / "results.json").write_text(json.dumps(cases, indent=2) + "\n")
assert (home / "db").read_bytes() == original_data
assert all(c["equal"] for c in cases), cases[-1]
for owner in ("control", "candidate"):
    script.write_text('''module_path=($1 $module_path)
zmodload wshdirectory || exit 2
ZSHZ_CMD=jump
source $2
zshz --add "$HOME/project space" || exit 3
zshz --add "$HOME/project space" || exit 4
jump space || exit 5
[[ $PWD == "$HOME/project space" ]] || exit 6
[[ ${#${(M)chpwd_functions:#_zshz_chpwd}} == 1 ]] || exit 7
print -r -- "WSH_JUMP:$PWD"
''')
    (home / "db").write_bytes(original_data)
    run = subprocess.run([binary, "-df", script, module, prototype / f"{owner}.zsh"],
                         env=env, capture_output=True, timeout=5)
    (output / f"{owner}-persistence.stdout").write_bytes(run.stdout)
    (output / f"{owner}-persistence.stderr").write_bytes(run.stderr)
    assert run.returncode == 0 and not run.stderr, (owner, run)
    assert b"WSH_JUMP:" in run.stdout
    assert (home / "db").read_bytes() != original_data
print(f"PASS: {len(cases)} actual Zsh-z comparisons")
