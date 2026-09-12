# Wsh security boundaries

Wsh's theme format separates appearance from executable shell code. Installation and updates belong to the system package manager. These boundaries apply to the current native implementation; native packages have not yet been published.

## Non-executable themes

A theme is TOML data selecting layout, named colors, bounded literals and supported component settings. The installed components are context, directory, Git state, command duration and the prompt character. Definitions cannot execute commands, register hooks, include files, read environment variables, access the network or load native code. The [theme guide](THEMES.md) and [schema](schemas/theme.schema.json) describe the supported fields.

The [native validator](native/theme.c) limits a definition to 64 KiB, rejects unknown fields and control characters, and checks component membership, unique layout entries, required fields and field-specific bounds. The renderer escapes theme literals and runtime values for Zsh prompt expansion and supplies styling itself. Theme text cannot provide raw terminal controls. A definition can still display misleading words or symbols; validation does not endorse its appearance or claims.

Theme selection supports bundled names and local files. There is no public theme directory, publisher-namespace service, signed directory index or automatic theme-update service. A contributed directory remains a [future feature](FEATURES.md#remaining-work).

## Executable configuration and plugin ownership

User startup files, executable themes, plugins, external modules and launched programs run with the user's normal authority. Wsh does not sandbox that code. Its own shell additions, helper and integration are trusted executable package components.

Supported unmodified upstream plugins can hand ownership to Wsh's implementation. The catalog checks known file contents first; a bounded local Git check can establish upstream provenance for uncataloged copies. Modified or unverified implementations remain external. This identifies which implementation should run; it does not certify arbitrary plugin code as harmless. [Component compatibility](VENDORED-COMPONENTS.md) records the recognized families and preserved settings.

`wsh --doctor` diagnoses configuration and ownership without editing startup files. It is not a package-authenticity or general trust audit. `wsh --wsh-version` reports compiled identity; its build label does not authenticate the executable or verify installed resources.

## Package authenticity and updates

The [release contract](RELEASES.md) requires two isolated builds with identical RPM and installation-manifest bytes, exact-commit validation and GitHub build provenance for official artifacts. A checksum establishes integrity; provenance binds the artifact to its source and workflow. Two workers in the same trust domain establish repeatability, not independent trust in their shared inputs.

Local builds are unsigned development artifacts. RPMs currently have no separate maintainer GPG signature, and no hosted DNF repository is configured. Source RPMs rebuilt by users or downstream distributions have their own build identities; they do not inherit official binary provenance.

DNF owns installation, upgrades and downgrades. Wsh's startup has no self-update check, bootstrap installer or activation record. User configuration, history and profile data remain outside the package-owned resources.

## Login and recovery boundaries

The system-owned executable starts without per-user activation state. Bundled Zsh modules are linked into it, and unavailable optional integration or helper resources preserve the tested native shell path. Ordinary RPM removal refuses while local accounts name the registered shell paths.

Missing executables or required system libraries, broken user startup code, PAM failures and display-manager failures require recovery at their respective owners. Administrators must check remote identity directories and nonstandard shell aliases; bypassing package scriptlets bypasses the removal guard. See [installation and recovery](NATIVE-INSTALLATION.md#package-updates-and-recovery).

## Verification evidence

- [Theme parsing and rendering qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-render-2026-09-08/theme-parser-report.md) and [renderer parity](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/native-render-2026-09-08/renderer-report.md) cover accepted definitions, rejected inputs and escaped output.
- [Installed manifest tests](tests/native-manifest.py) cover resource inventory and tampering. [Release validation](DEVELOPMENT.md#ci-and-release-authorization) checks the current build and public-install paths.
- [Fedora package qualification](https://github.com/wakamex/wsh/blob/c7af8c63bcecb7d276ab6ae92896b0e5f90a66c3/benchmarks/release-qualification-2026-09-10/report.md) covers PAM login, job control, package transactions, recovery and reboot with enforcing SELinux. It does not establish a complete graphical GDM session.
- [Profiling](PROFILING.md#privacy-and-bounds) documents private storage, bounded input and the command, environment and path data excluded from default traces.

Historical launcher activation, bootstrap and manager rollback experiments describe the retired distribution. Current native guarantees come from the package and installed-shell checks above.
