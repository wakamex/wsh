# Native release contract

A native release publishes one x86-64 Fedora RPM, its complete installation manifest, two build records, checksums and GitHub build provenance. The package pairs the pinned Zsh source and Wsh C implementation with the tested integration and theme files. System packages own installation, upgrades and downgrades. Shell startup performs no update work.

## Source and build identity

`VERSION` is the product version. The native source lock records upstream bytes, patches and native inputs. The SDK extends an immutable Rocky Linux 8.10 image with signed RPM files selected by exact digest, installs them offline and checks the complete resulting package inventory. The manifest records source revision, compiler, flags, SDK input identity, target, system-library requirements and every payload file. The supported build floor is glibc 2.28; package-manager compatibility is separately qualified on Fedora.

`build/test-reproducible-development-bundles.zsh` builds two fresh worktrees without shared compiler or build caches and compares the native manifests and RPMs. Normalized ownership, modes, ordering, compression metadata, source timestamp and RPM macros are part of the build contract. Local results are unsigned development artifacts.

## Release authorization and publication

The main-push `release-eligible / validate` check must pass on the exact release commit. The annotated version tag must match `VERSION`, resolve to that commit and include its nonempty `release-notes/vMAJOR.MINOR.PATCH.md`. Pushing that tag requires explicit release authorization.

The publication workflow repeats validation and eligibility checks, builds on two fresh workers, compares the two deterministic product files, retains both build records, attests all staged assets and creates the immutable GitHub Release with the committed notes. A rerun validates existing immutable assets and provenance instead of replacing them. Public verification downloads the actual RPM, verifies its bytes and exercises native login after package installation.

Agreement between two GitHub workers demonstrates repeatability within the same trust domain. It does not independently establish the trustworthiness of their shared inputs. The published provenance is the authenticity evidence; a bare SHA-256 checksum is only an integrity check. RPMs do not currently have a separate maintainer GPG signature or a hosted DNF repository.

## Updates and login compatibility

Users explicitly select packages through DNF. Native Wsh has no second updater, bootstrap installer, activation record or `wshctl`. Existing shells retain their linked executable and modules across replacement. Changes to external modules, autoload functions or helper protocols require compatibility or an explicit restart policy before shipping.

Ordinary removal refuses while a local `/etc/passwd` entry uses `/usr/bin/wsh` or `/bin/wsh`. Administrators must check remote identity directories and nonstandard aliases separately. Forced scriptlet bypass and deletion of system binaries or required libraries remain system-administration actions outside that guard.

The native release assumes fresh installations; migration from older Wsh releases is not a release requirement. The [installation guide](NATIVE-INSTALLATION.md) covers native commands, account-shell setup and recovery. The earlier release contract and its evidence remain available in the v0.3.1 source history. Publication of the native architecture requires a new authorized release; editing this workflow does not publish it.
