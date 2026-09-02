# Runtime protocol version 1

The bundled Zsh adapter and matching `wsh-runtime` communicate over one pair of inherited pipes using newline-delimited JSON. Every line is at most 65,536 bytes, every message carries `version: 1`, and unknown fields or message types are rejected. The runtime accepts at most 32 queued events, owns at most one Git child, and retains only the newest pending refresh.

Paths cross the protocol as lowercase hexadecimal filesystem bytes. This avoids JSON quoting ambiguity and preserves non-UTF-8 Linux paths. Rendered prompts also cross as hexadecimal bytes. Git snapshot paths remain hexadecimal, while fields intended for display are encoded by the trusted renderer before they reach Zsh.

## Requests

```json
{"type":"ping","version":1,"id":1}
{"type":"refresh","version":1,"id":2,"generation":1,"cwd_hex":"2f746d70","exit_status":0,"duration_ms":null,"privileged":false,"reset_transient":false}
{"type":"cancel","version":1,"id":3,"generation":1}
{"type":"shutdown","version":1,"id":4}
```

Request IDs correlate direct responses. Generations identify prompt state. Refresh generations must increase strictly within a runtime process. A newer refresh cancels active work and replaces any older pending refresh. `cancel` suppresses publication through the named generation and clears pending work. `reset_transient` clears renderer memory used by changed-only components, including the behavior expected after `clear`.

## Responses

```json
{"version":1,"type":"ready","theme":"minimal"}
{"version":1,"type":"pong","id":1}
{"version":1,"type":"cancelled","id":3}
{"version":1,"type":"error","id":2,"error":"refresh generation is stale"}
{"version":1,"type":"stopping","id":4}
```

A completed refresh emits one `snapshot` response containing the same request ID and generation, `prompt_hex`, `rprompt_hex`, and a complete Git snapshot. A cancelled or superseded generation emits no snapshot.

## Git snapshot schema 1

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | `1` |
| `generation` | integer | Refresh generation that produced the snapshot |
| `cwd_hex` | string | Exact working-directory filesystem bytes |
| `found` | boolean | A Git worktree was found |
| `root_hex` | string or null | Exact worktree-root filesystem bytes |
| `branch` | string or null | Current local branch |
| `detached_sha` | string or null | Seven-character detached commit ID |
| `exact_tag` | string or null | Lexically first exact tag when detached |
| `staged` | boolean | Index differs from `HEAD` |
| `modified` | boolean | Tracked worktree content differs from the index |
| `untracked` | boolean | At least one untracked path exists |
| `ahead` | integer | Commits ahead of the configured upstream |
| `behind` | integer | Commits behind the configured upstream |
| `operation` | string or null | `rebase`, `merge`, `cherry-pick`, `revert`, or `bisect` |
| `worktree` | boolean | Snapshot describes a worktree rather than a bare repository |

The provider publishes a complete snapshot after one optional-lock-safe `git status --porcelain=v2 --branch --untracked-files=normal --ignore-submodules=dirty` process plus bounded direct reads for repository identity, exact tags, and operation markers. It caps Git output at 4 MiB and kills work after two seconds or cancellation.

## Publication and repaint rules

The adapter keeps the last accepted prompt visible while a replacement is collected. It accepts only the current generation, compares the newly rendered `PROMPT` and `RPROMPT` with the last accepted pair, and changes both together with one ZLE repaint only when either changed. The initial fallback prompt is editable before the first snapshot. EOF or a malformed response disables the runtime path without blocking command entry. Normal shutdown cancels and reaps active work before the runtime acknowledges `stopping`.
