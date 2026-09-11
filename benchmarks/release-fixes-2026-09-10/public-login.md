# Public RPM login verification passes in Fedora

The corrected publication command installs the retained native RPM in a fresh Fedora 44 container, creates a fresh account with `/usr/bin/wsh` as its shell, and prints `WSH_LOGIN_OK` through `su -l`. The workflow sends the guest script through a quoted heredoc with container stdin enabled, so guest variables reach the guest shell unchanged.

The real container test also established that Fedora's image lacks `su`. DNF identifies `util-linux` as its provider, so the workflow explicitly installs that package alongside the RPM. Both defects belong to Wsh's release workflow. They are not upstream Zsh bugs.

`python3 tests/public-release-login.py` loads the actual workflow with PyYAML and exercises its command through real Bash and Zsh parsers. It verifies exact Podman arguments, preservation of guest variables despite an incompatible runner variable, the success marker and propagation of a failed guest login. External side effects are recorded or replaced only in this parser regression; the separate Fedora run used actual Podman, DNF, the retained RPM, useradd and su. Actionlint v1.7.12 accepted the changed workflows.

`public-login.json` records workflow/test source hashes, image identity, RPM hash and the passing log hash. The RPM is the previously qualified unsigned plugin-catalog floor artifact; this test did not build or publish a new package. Local test setup copied it into a private download directory and reset inherited SELinux categories to permit the disposable container to read it. No live account shell or installed host package changed.

The regression runs in the complete retained-evidence entrypoint, and CI explicitly installs its PyYAML dependency. The existing published-artifact check remains responsible for testing the RPM downloaded from a future actual release.
