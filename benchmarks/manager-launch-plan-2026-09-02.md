# Active launch must not reverify the complete bundle

Normal `wsh` startup currently hashes and inspects every installed payload file twice before starting the selected Zsh. The retained prompt and memory measurements launched the bundled Zsh and runtime directly, so their reported values are unchanged, but they do not cover this manager cost.

The baseline and intervention use the same manager source revision, content-addressed development bundle, bundled Zsh, CPU, command, warmup, repetitions, and forward/reverse order. Each observation measures 100 sequential `-f -c exit` launches. The direct control invokes the bundled Zsh, while the managed path resolves an already activated bundle through `wsh run`.

The smallest intervention is to keep complete payload verification at build, installation, activation, explicit verification, and rollback, while normal launch checks the previously recorded manifest identity and required entrypoint metadata without hashing unrelated payload files. The intervention passes when all correctness tests pass and the median managed overhead across the ten batch means is at most 2.0 ms per launch. An end-to-end interactive startup gate remains separate because this experiment isolates manager dispatch from prompt and provider work.

One implementation attempt is allowed for this hypothesis. If it misses the gate, profile manifest loading and process handoff before changing another factor.
