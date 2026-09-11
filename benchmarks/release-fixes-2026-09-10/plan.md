# Release-only correctness fixes

Baseline `31bf505` records two reproducible release defects. The public-login step fails during real Bash parsing before the intended guest-shell assertion; the native version command always prints development status. Fix and commit each independently.

For login verification, preserve the exact guest script through a quoted heredoc with container stdin enabled. Require the real YAML/Bash/Zsh regression to preserve literal guest variables, emit its success marker, and propagate a failing login. Also run the exact workflow container command against a retained native RPM in disposable Fedora. No live account shell or public release is changed.

For version identity, compile a validated development/release label through the existing build header. Require both labels through the actual C dispatcher, distinct build-cache identities, rejection of invalid build status, and independence from runtime environment, user startup and mutable installed metadata. Retain native argument/error behavior. The change does not alter the ordinary startup or editor path; timing benchmarks are unnecessary for this diagnostic string change. Rebuild an installed native shell and verify its version and shell interface.

Preserve historical evidence hashes if the locked source identity changes. Run the complete retained-evidence suite before finalizing the work. After two failed interventions at either behavior gate, audit the premise before another implementation attempt.
