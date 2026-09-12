# Build Wsh from a source RPM

`packaging/wsh.spec` compiles the pinned Zsh sources and Wsh C implementation inside the RPM build environment. The source RPM includes the Wsh sources, patches, vendored inputs, tests and pinned upstream archive. No prebuilt Wsh executable, Git checkout or network access is needed for the rebuild. This recipe currently targets x86-64 Fedora.

## Prepare the source package

From the repository, with Python 3 and rpmbuild installed:

```sh
python3 packaging/build-source-rpm.py /var/tmp/wsh-srpm
```

Use a new output directory. The generator verifies the cached upstream archive or downloads and verifies it before packaging, records the source revision and exact input hashes, and runs `rpmbuild -bs`. Development snapshots include `+dirty` in their identity when appropriate. `--status release` requires a clean worktree and selects release-mode diagnostics; it does not publish or authenticate an artifact. `--release` sets the RPM release field.

The generated source archives have fixed ordering, modes, ownership and timestamps. RPM itself also records build-environment metadata, including expanded source paths on current Fedora; compare source archives separately from the SRPM wrapper.

## Rebuild in the target distribution

Install the source RPM's declared build dependencies in a disposable Fedora build environment, then rebuild as an unprivileged user:

```sh
rpmbuild --rebuild /path/to/wsh-VERSION-RELEASE.src.rpm
```

COPR and Mock can consume the same source RPM. The build uses the target distribution's normal compiler/linker flags and RPM post-processing, including debug package generation. It builds the reference and native shells from source, runs upstream Zsh tests and the shared Wsh installation checks, and refreshes the payload inventory after RPM has finished processing the installed files. The inventory refresh also runs when checks are explicitly skipped; qualification requires checks enabled.

`tests/source-rpm.py SOURCE_RPM` inspects the actual package, verifies its source-only contents and dependencies, and tests missing or altered offline sources. `build/check-native-installation.zsh` is shared with the canonical installation suite. Source-package preparation generates a fresh source inventory; changes covered by the native lock must also update that lock.

For the local check used by CI, run `./packaging/test-source-rpm.zsh NEW_OUTPUT` with Podman, Zsh, Python 3 and rpmbuild installed. It prepares the dependency image, rebuilds with networking disabled and retains the image identity, package inventory, build logs and output RPMs. See the [Fedora rebuild and login qualification](../benchmarks/source-rpm-2026-09-11/report.md) for the tested result.

## Artifact identity and existing publication

A distro rebuild has its own compiler, dependencies, package processing and installation identity. It does not inherit the glibc 2.28 floor or GitHub attestation of the separately built canonical package. `packaging/wsh-native.spec` and `packaging/build-rpm.py` remain the canonical payload-packaging path and disposable transaction-fixture tools; `packaging/wsh.spec` is the source-build recipe. No COPR project, repository, release trigger or publication is configured by preparing an SRPM.
