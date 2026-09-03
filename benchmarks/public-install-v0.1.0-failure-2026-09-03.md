# v0.1.0 failed before activation because its installer bypassed the relocatable Zsh startup path

The first real invocation of the published `v0.1.0` bootstrap downloaded its immutable GitHub Release assets and verified the native tools, but installation stopped during the candidate Zsh smoke test. The extracted shell searched for `zsh/datetime` under its original `/workspace/build/portable/glibc-2.28/...` build prefix, failed to load the module, and created no activation state.

```text
zsh:1: failed to load module `zsh/datetime': /workspace/build/portable/glibc-2.28/zsh/zsh-5.9.2/lib/zsh/5.9.2/zsh/datetime.so: cannot open shared object file: No such file or directory
error: candidate Zsh smoke test failed with exit status: 1
```

The bundle already included a relocatable `.zshenv` that derives `module_path` and `fpath` from `WSH_BUNDLE_ROOT`, and normal `wsh run` supplied that root and the bundled `ZDOTDIR`. The installer instead invoked Zsh with `-f`, which disables startup files, and omitted both variables. Local and compatibility-floor tests had exercised the normal manager launch path and fixture archives backed by the host Zsh, so neither reproduced the installed release path.

The smallest fix invokes the candidate with the same `-d`, `WSH_BUNDLE_ROOT`, and `ZDOTDIR` contract used by normal launch. The transaction fixture now rejects the wrong flags or missing relocation variables. GitHub immutable releases prevent replacing `v0.1.0`; the corrected candidate is `v0.1.1`.
