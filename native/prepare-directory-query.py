#!/usr/bin/env python3
"""Hold Zsh-z lifecycle/output fixed while replacing the matching kernel."""
from pathlib import Path
import hashlib
import json
import sys

root=Path(__file__).resolve().parents[1];out=Path(sys.argv[1]).resolve();out.mkdir(parents=True)
original=(root/'third_party/zsh-z/z.plugin.zsh').read_text()
# Both fixtures receive the same stable clock, outside the candidate boundary.
control=original.replace('local now=$EPOCHSECONDS','local now=${WSH_QUERY_NOW:-$EPOCHSECONDS}')
start=control.index('    for line in $lines; do',control.index('  _zshz_find_matches() {'))
end=control.index('    # Return 1 when there are no matches',start)
candidate=control[:start]+'    wsh-directory-query || return\n\n'+control[end:]
(out/'control.zsh').write_text(control);(out/'candidate.zsh').write_text(candidate)
(out/'metadata.json').write_text(json.dumps(dict(upstream_sha256=hashlib.sha256(original.encode()).hexdigest(),control_sha256=hashlib.sha256(control.encode()).hexdigest(),candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest(),removed_kernel_lines=len(control[start:end].splitlines())),indent=2)+'\n')
