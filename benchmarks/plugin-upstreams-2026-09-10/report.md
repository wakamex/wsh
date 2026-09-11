# Daily upstream check passes all six monitored file sets

The live GitHub API check found all six configured upstream file sets in the existing catalog. The workflow checks daily at 13:23 UTC and on manual dispatch. Relevant new bytes or a check error fail the run; unrelated repository changes pass. It retains upstream revisions and source bytes for review without executing downloaded code or updating Wsh automatically.

The checker resolves one immutable commit per repository/branch and validates the returned file path, encoding, length and Git blob identity before comparing complete file sets. The live result and decoded source bytes are retained in `evidence.tar.gz`. Tests also cover known, changed and error outcomes, malformed file responses, wrong paths and incorrect blob identities. Actionlint v1.7.12 accepted the workflow.

| Component | Official upstream repository | Checked commit | Result |
| --- | --- | --- | --- |
| Autosuggestions | zsh-users/zsh-autosuggestions | 85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5 | Known file bytes |
| History substring search | zsh-users/zsh-history-substring-search | 14c8d2e0ffaee98f2df9850b19944f32546fdea5 | Known file bytes |
| Oh My Zsh history substring search | ohmyzsh/ohmyzsh | c6e66edee824d83e84473ec666917b58323630df | Known file bytes |
| Syntax highlighting core and main parser | zsh-users/zsh-syntax-highlighting | 2fc57d63067c18b1100ecdbf684fa5baf49459d1 | Known file bytes |
| Oh My Zsh directory jumping | ohmyzsh/ohmyzsh | c6e66edee824d83e84473ec666917b58323630df | Known file bytes |
| Oh My Zsh Git prompt collector | ohmyzsh/ohmyzsh | c6e66edee824d83e84473ec666917b58323630df | Known file bytes |

GitHub sends its normal Actions notifications according to account preferences. An email rule can suppress successful runs of `Plugin upstream changes`; GitHub also offers account-wide failure-only Actions notifications. The workflow does not implement a second notification service. Scheduled execution begins after this workflow reaches the default branch. This qualification exercised the local checker and workflow validator; it did not dispatch a remote workflow or test email delivery.

Reproduce the live check with `python3 build/check-plugin-upstreams.py OUTPUT`, and run `python3 tests/plugin-upstream-monitor.py` for the offline response tests. The workflow gives its token read-only contents permission and retains each run's artifact for 30 days. Review a changed file set, decide which upstream behavior belongs in native Wsh, and add the reviewed source snapshot to the fast-path catalog when its handoff is qualified.
