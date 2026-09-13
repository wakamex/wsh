# Fedora source-package review

The source RPM is the Fedora packaging submission target. The canonical GitHub artifact assembler consumes an already-built payload and is a separate release mechanism; its spec is not a Fedora source-package submission.

## Rules and package behavior

This review uses the [Fedora guidelines](https://forge.fedoraproject.org/packaging/guidelines/src/commit/74a097085468741509917169437e61fb67724324/guidelines/modules/ROOT/pages/index.adoc) and the accompanying review, licensing, source-reference and scriptlet rules. Formal Fedora acceptance still requires an independent package review and a sponsored maintainer.

| Area | Implementation |
| --- | --- |
| Source provenance | Release-mode SRPMs download the exact public Wsh commit archive and preserve its bytes. Generated source identity is a separate Source2. Zsh uses its immutable commit archive with a verified digest. Development SRPMs explicitly contain a local snapshot and are not source-matching release submissions. |
| Offline build | All sources and patches are included. The unprivileged rebuild has networking disabled. |
| Flags and debug packages | The recipe uses Fedora optflags and build_ldflags, leaves normal RPM processing enabled, and produces debug packages. |
| Filesystem | The shell is `/usr/bin/wsh`, its private helper is `/usr/libexec/wsh/wsh-runtime`, and shell functions, themes and integration are under `/usr/share/wsh`. No system Zsh executable or function directory is replaced. |
| Licensing | Wsh and MIT plugins use MIT, Zsh uses MIT-Modern-Variant, its OpenSSH-derived ID wrappers use ISC, `_qdbus` uses GPL-2.0-only, and history substring search and highlighting use BSD-3-Clause. Separate license texts have distinct names and are tagged `%license`; the history-search source preserves its complete inline notice. Build-only files are not included in the binary-package License expression. |
| Bundling | The patched TOML parser and four plugin-derived implementations have versioned `Provides: bundled(...)` entries. The rationale and upstream identities are below. |
| Removal | Like Fedora Bash, Zsh and Fish, the package registers shell paths and removes those registrations on final uninstall. It does not change account records or veto removal. Administrators must change account shells first. |
| Architecture | The source spec has no artificial x86-64 restriction. Qualification still determines which targets Wsh advertises as supported. |
| Documentation | The package includes a Wsh manual page and a package changelog. |

## Patched tomlc17

Wsh is the upstream owner of this build decision. The source comes from cktan/tomlc17 commit `64a063b8636a4b48d142f978270f5e53e605e240`, dated 2026-08-22. Wsh applies `native/tomlc17-wsh.patch` to private build copies for checked unsigned-64-bit theme thresholds and the qualified numeric-token and allocator fixes. The current upstream Wsh build has no system-tomlc17 mode because an arbitrary system build does not supply that interface. The package records the bundled source identity for vulnerability tracking. Revisit system linkage when a packaged implementation supplies the tested interface; system Jansson, zlib, ncurses, PCRE2 and libcap are already used.

## Plugin-derived code

The generated native adapters and retained plugin lifecycle code are integrated Wsh implementations with no system-plugin build mode. Replacing those build inputs with arbitrary installed versions would change the generated adapter contract. The spec therefore also records autosuggestions v0.7.1, history substring search after v1.1.0 at `14c8d2e`, highlighting's 0.8.1 development snapshot at `2fc57d6`, and Zsh-z 2.0 as carried by Oh My Zsh `9112b53`. Their exact hashes and transformations remain in [component provenance](../VENDORED-COMPONENTS.md). Additional catalog and Git-prompt snapshots are comparison data, never executed as upstream programs.

## rpmlint interpretation

Run rpmlint on the source RPM and every output RPM, including debuginfo and debugsource. Retain raw output. Explain narrowly scoped false positives rather than editing exact upstream recognition bytes to silence a scanner.

- Zsh's `gettempname` calls `mktemp` to choose a name; its file-opening callers use exclusive creation and its FIFO caller uses `mkfifo`. Review the real callers before treating the symbol warning as a temporary-file vulnerability.
- Autoload functions, sourced adapters and byte-comparison snapshots deliberately have mode 0644. Their upstream shebangs do not make them independently executed programs. Changing recognition snapshots would defeat exact upstream identification.
- The highlighter's `.version` and `.revision-hash` are upstream metadata files used by its lifecycle.
- `gethostbyname` is part of upstream shell networking functionality; its presence is not an automatic package rejection.
- Source2 is generated build identity, so it intentionally has no download URL. Development Source0 is also a local snapshot; release Source0 has the exact public archive URL.
- Equal runtime/reference bytes are hardlinked during source-package installation. License duplication across payload and `%license` is permitted.

## Upgrade boundary

The filesystem reorganization changes the resource paths captured by a running shell. Restart Wsh sessions after upgrading from the v0.4.0 layout before continuing interactive work. A running process retains its executable and linked modules, but its saved paths to autoload files and the optional helper belong to the old layout. This release boundary uses an explicit restart policy rather than retaining a second installation tree.

## Validation status

The offline Fedora 44 rebuild, both upstream Zsh suites, complete installed checks and real-RPM container installation passed. The glibc 2.28 installed suite and Fedora QEMU login, recovery, reboot and transaction checks also passed. The [qualification report](../benchmarks/fedora-packaging-2026-09-13/report.md) retains commands, hashes and raw results.

Across the source RPM and all three binary RPMs, unfiltered rpmlint reports 24 errors and nine warnings. The errors are the sourced/reference shebangs and upstream `mktemp` symbol discussed above. With the reviewed filters, the gate reports zero errors and six warnings: five permitted license duplicates and the development Source0's local filename. Release-mode preparation uses a public Source0 URL.
