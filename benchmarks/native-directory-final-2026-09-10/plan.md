# Native directory owner qualification

The remaining question is whether the faster native directory owner preserves confirmation and file-mount persistence behavior and can replace the installed implementation without startup regressions. Baseline source is 07f91c7, with unsigned history installation 574e93e006915e120ead037ce844d1c7df4da37000defb47517d6a0a7d1c83ad. The pinned Zsh-z source remains the behavioral reference.

1. Reproduce the missing root-removal confirmation in an actual PTY. Invoke Zsh's existing read builtin before taking the database lock. Require confirmation parity, unchanged database after rejection or interruption, and an independently acquired actual Zsh lock while waiting. Run normal and address/undefined sanitizer builds.
2. Reproduce rename failure against an actual bind-mounted database. Test the smallest locked copy fallback against the pinned owner, preserving ordinary atomic replacement. Require successful update of the mounted inode, mixed-writer interoperability, and explicit failure for unsupported write errors.
3. Select the native owner only after query, persistence, lifecycle, completion, ownership, and installed startup tests pass. Require the existing 20% lookup improvement and no more than 3 ms paired p95 installed startup regression, using 50 alternating pairs and matching instrumentation. Preserve original plugin recognition and unknown user implementations.
4. Build and test the combined selected components on glibc 2.28, following the existing native floor SDK and installation contracts. Retain source and build identities, raw results, and the exact exercised scope. These remain unsigned local development artifacts.

Each hypothesis is limited to two failed interventions or two hours before auditing its premise. A failed correctness gate prevents adoption; it does not justify broadening compatibility machinery. Commit completed slices separately. Do not push, publish, or alter the user's shell configuration.
