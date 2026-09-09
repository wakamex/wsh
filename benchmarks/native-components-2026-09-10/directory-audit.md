# Directory selection audit

The first absolute-path comparison selected the highest-ranked path instead of the reference's common root. The reference walks a Zsh associative array, so database order is insufficient to preserve this behavior. Reusing Zsh's parameter-table ordering fixed that case. The second run passed 60 cases before uncommon matching selected `/` instead of the reference's tab-containing path.

After those two failed correctness interventions, the next hypothesis is narrower: the native call to `getmatch` omitted the substring and longest-match flags used by Zsh's `${value//pattern/}` operation. Add those flags and repeat the same corpus. This is an API-translation correction, with one further attempt before retaining the candidate as incomplete. No performance comparison is admissible while selection differs.

An earlier run used relative fixture paths and failed its control persistence assertion. Its apparent query agreement was invalid because both sides searched nonexistent relative paths. It is excluded; subsequent runs use absolute paths.
