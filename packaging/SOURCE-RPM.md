# Build Wsh from a source RPM

`packaging/wsh.spec` compiles the pinned Zsh sources and Wsh C implementation inside the RPM build environment. The source RPM includes the Wsh sources, patches, vendored inputs, tests and pinned upstream archive. No prebuilt Wsh executable, Git checkout or network access is needed for the rebuild. The recipe is qualified on x86-64 Fedora; it does not artificially exclude other architectures from source builds.

## Prepare the source package

From the repository, with Python 3 and rpmbuild installed:

```sh
python3 packaging/build-source-rpm.py /var/tmp/wsh-srpm
```

Use a new output directory. The generator verifies the cached upstream archive or downloads and verifies it before packaging, records the source revision and exact input hashes, and runs `rpmbuild -bs`. Development snapshots include `+dirty` in their identity when appropriate. `--status release` requires a clean worktree and selects release-mode diagnostics; it does not publish or authenticate an artifact. `--release` sets the RPM release field.

Release mode downloads the exact public GitHub commit archive, checks its source files against the clean checkout, and keeps generated identity in a separate Source2 file. The commit must already be public. Development mode creates a local source snapshot with fixed ordering, modes, ownership and timestamps; it is marked as development and is not an upstream-source matching submission. RPM itself also records build-environment metadata, including expanded source paths on current Fedora; compare source archives separately from the SRPM wrapper.

## Rebuild in the target distribution

Install the source RPM's declared build dependencies in a disposable Fedora build environment, then rebuild as an unprivileged user:

```sh
rpmbuild --rebuild /path/to/wsh-VERSION-RELEASE.src.rpm
```

COPR and Mock can consume the same source RPM. The build uses the target distribution's normal compiler/linker flags and RPM post-processing, including debug package generation. It builds the reference and native shells from source, runs upstream Zsh tests and the shared Wsh installation checks, and refreshes the payload inventory after RPM has finished processing the installed files. The inventory refresh also runs when checks are explicitly skipped; qualification requires checks enabled.

`tests/source-rpm.py SOURCE_RPM` inspects the actual package, verifies its source-only contents and dependencies, and tests missing or altered offline sources. `build/check-native-installation.zsh` is shared with the canonical installation suite. Source-package preparation generates a fresh source inventory; changes covered by the native lock must also update that lock.

For the local check used by CI, run `./packaging/test-source-rpm.zsh NEW_OUTPUT` with Podman, Zsh, Python 3 and rpmbuild installed. It prepares the dependency image, rebuilds with networking disabled and retains the image identity, package inventory, build logs and output RPMs. See the [Fedora packaging qualification](../benchmarks/fedora-packaging-2026-09-13/report.md) for the tested result.

## Artifact identity and existing publication

A distro rebuild has its own compiler, dependencies, package processing and installation identity. It does not inherit the glibc 2.28 floor or GitHub attestation of the separately built canonical package. `packaging/wsh-native.spec` and `packaging/build-rpm.py` remain the canonical payload-packaging path and disposable transaction-fixture tools; `packaging/wsh.spec` is the source-build recipe. Preparing an SRPM does not publish it. The hosted COPR channel is managed separately below.

The [Fedora review](FEDORA-REVIEW.md) records the policy checks and scoped rpmlint interpretations. CI retains raw lint output, requires the reviewed lint gate, and tests installation, login and removal against the actual RPM in a disposable container.

## COPR publication

The `wakamex/wsh` project builds Fedora 44 x86-64 source RPMs with build networking disabled. COPR signs the resulting packages and hosts DNF metadata. The [repository qualification](../benchmarks/copr-2026-09-13/report.md) records the exact source commit, build and package identities, signature checks and real installation/login results. This channel uses Fedora build dependencies and flags; the canonical GitHub artifact contract remains separate.

For an explicitly authorized update, run the current-source and relevant installed checks, push the clean source commit to `main`, require `release-eligible / validate` to pass on that exact commit, and confirm remote `main` still matches. Generate a release-mode SRPM from that checkout with `packaging/build-source-rpm.py`. Increase `--release` for a packaging update at the same product version so DNF selects the new package; the first COPR package uses `0.4.0-1.fc44`.

Submit the resulting single SRPM with:

```sh
copr-cli build wakamex/wsh /path/to/wsh-VERSION-RELEASE.src.rpm --chroot fedora-44-x86_64 --enable-net off --nowait
copr-cli status BUILD_ID
```

A successful build publishes its packages automatically. Require the full `%check` suite, then exercise DNF installation and upgrade from the hosted repository in the disposable VM, with package signature checking enabled. Repeat login, job-control, reboot and removal checks when packaging or startup changes. Retain the build URL, source identity, signed package hashes, effective repository configuration and test results. Preparing or submitting a COPR build does not authorize a new GitHub version tag.
