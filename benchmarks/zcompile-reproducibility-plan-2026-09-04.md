# Zsh compiled-function reproducibility experiment

The clean two-build gate for Wsh revision `7fefaa6b7083c3fd174536b240a2dc94005a79d3` produced different manifests before it compared archives. The only payload difference was `share/wsh/defaults/zsh-syntax-highlighting/highlighters/line/line-highlighter.zsh.zwc`: worker A recorded SHA-256 `d5f2768e763c90dd34e12ed168b1b07f608f2dccf95f9c2d0fe8bc0923a0dc98`, while worker B recorded `e7404267c958facec01acc67b49d54416132994db176d1de3a17b74e6159fa2f` from the same committed source and byte-identical Zsh executables.

`cmp -l` isolated both differences to the last two bytes of each byte-order copy in the compiled dump. Source inspection found that `write_dump()` rounds the program length to a whole `wordcode` and writes that rounded length directly from a heap allocation. The logical program does not initialize its trailing alignment bytes.

The smallest source-level counterfactual writes the logical initialized length, then writes explicit zero padding to preserve the existing file layout. A build-artifact normalizer would hide the native uninitialized read, and omitting the small highlighter's compiled form would leave the same defect in any other program whose length is not word-aligned.

The change passes when:

- The old Zsh fails a focused fixture because its compiled dump has nonzero trailing alignment bytes.
- The patched Zsh compiles the same source in two isolated directories to byte-identical output and both byte-order copies end in zero padding.
- All 75 upstream Zsh test scripts pass with no failures and the same 2 existing skips.
- The complete Wsh suite passes at the glibc 2.28 floor.
- Two clean builds of one committed revision produce byte-identical manifests, archives, launchers, installers, and bootstrap scripts.
