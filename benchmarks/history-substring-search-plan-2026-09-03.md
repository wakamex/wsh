# History substring search should become a measured Wsh default without duplicate runtime ownership

The current clean bundle `6c41e1dd2a15e67d1558178222a913a626dfbfa5ae7a7e358b3c74f2db9962ed` does not provide substring history search unless user configuration loads an executable plugin. The retained coexistence experiment found that the three requested ZLE plugins work together but add 23.206 ms at p90 as a group. The first default experiment isolates history substring search and uses upstream commit `14c8d2e0ffaee98f2df9850b19944f32546fdea5` as the authoritative implementation.

## The smallest implementation bundles the established upstream code

Wsh vendors the exact upstream `zsh-history-substring-search.zsh` file with its BSD-3-Clause notice and records its source revision and digest. A small adapter loads it after the user's `.zshrc`, preserves its documented configuration variables, and binds common Up and Down terminal sequences only when their current widgets are undefined or belong to the ordinary Zsh, Oh My Zsh, or history-substring-search behavior being replaced. Unrelated custom bindings remain untouched.

If both history-substring-search widgets came from a 29,692-byte regular file whose complete contents match the pinned upstream file or the pinned Oh My Zsh copy, the adapter removes the implementation's known temporary highlight hooks and reloads the bundled copy. The comparison uses one bounded `sysread` per candidate or reference and exact equality without starting a helper process. The bundled functions and widgets then own runtime behavior. Wsh records that replacement so a later doctor command can advise removing the redundant plugin declaration and its source-time cost.

An existing implementation from an unknown or modified source remains active and the bundled copy does not load. This is an ambiguity, not an automatic takeover. A user can disable the default explicitly before the adapter runs.

## Correctness gates cover editing semantics and ownership

The candidate passes only when:

- A clean configuration gets working case-insensitive substring search through Up and Down.
- Consecutive Up presses select progressively older matching entries, Down returns toward newer entries, and a missing query remains unchanged.
- The documented highlight, uniqueness, fuzzy, prefix, and timeout variables set by user configuration remain available to the bundled implementation.
- Current pinned upstream and Oh My Zsh copies are replaced by bundled function definitions with one widget owner and no retained history-substring-search hook duplication.
- An unknown implementation and an unrelated custom arrow binding remain untouched and are reported as external ownership or preserved binding state.
- Explicit disablement loads no bundled widget.
- History substring search continues to compose with the pinned autosuggestions and syntax-highlighting implementations in their supported load order.
- Existing prompt, runtime, hook, Ctrl-C, exit-status, and cleanup tests continue to pass.

## Performance gates separate the normal and compatibility paths

The startup benchmark runs 5 warmups followed by 20 forward-order and 20 reverse-order launches on CPU 0. It records the first editable prompt for clean, disabled, and recognized-external configurations. The pre-change bundle supplies clean and external-plugin baselines under the same harness.

The normal bundled default passes when its p90 adds at most 4 ms over the candidate's disabled path, starts no helper process, and starts no process during a settled search interaction. The recognized takeover path passes when its p90 adds at most 6 ms over the pre-change external-plugin path and starts no comparison helper or later search process. The bundled plugin file must be byte-identical to the recorded upstream file, so accepted editing-path performance is the upstream implementation's performance rather than a separate Wsh rewrite.

The first direct bundled implementation took 7.336 ms over its disabled p90 and missed the 4 ms gate. Moving the source out of a helper function did not remove the cost. Profiling isolated 5.36 ms in eight guarded bindings across the `emacs` and `viins` maps. Restricting the adapter to the active `main` map and its two terminfo bindings reduced that helper to 1.56 ms. Precompiling the pinned source with the bundled Zsh then reduced the complete normal path to 3.654 ms over disabled and passed the original gate. The digest-based compatibility path remained 7.825 ms slower than the pre-change external path and missed its 6 ms gate. A byte-at-a-time `read` counterfactual was also rejected after adding 21.660 ms. A 10,000-iteration probe found that a single bounded `sysread` took about 0.028 ms per file while `read` took about 13.81 ms per file, so the accepted candidate uses the bulk builtin and exact equality. A failure requires revisiting the feature or gate before adding a native plugin loader, general ZLE broker, or `.zshrc` parser.
