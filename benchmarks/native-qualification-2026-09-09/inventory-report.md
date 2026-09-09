# Native ownership and retained migration decisions

The selected native installation executes C for the shell entrypoint, tools and prompt helper. Zsh owns language, startup files, ZLE and job control; one C helper per shell owns bounded asynchronous Git work and rendering. Native login no longer runs the Rust launcher or reads activation records. Existing complete Zsh plugins remain selected after the bounded component comparisons.

| Responsibility | Selected owner and remaining cost |
|---|---|
| Language, startup, editor, job control and terminal markers | Locked upstream Zsh plus the native patch queue; bundled modules linked into each executable, external loader preserved |
| Wsh invocation, diagnostics, foreground startup and profiling | 1,033 lines of Wsh-owned native C additions |
| Git, themes, rendering, protocol, tracing and helper lifecycle | 1,642 lines of Wsh-owned C; one per-shell helper and one worker thread |
| Native headers | 127 lines across retained native support headers |
| Integration callbacks and feature composition | 685 lines of maintained integration Zsh; component/function attribution still uses shell callbacks |
| Complete interactive plugins | 7,267 lines of pinned Zsh plugin/function source; partial C kernels are not substituted automatically |
| Theme/runtime parsing libraries | 23,485 lines of vendored TOMLc17/yyjson source and headers, plus the separately documented TOMLc17 build patch; system Jansson supplies profile JSON |
| Supported legacy distribution | 7,040 lines of Rust source/tests under `crates`; launcher, installer, updater, reporter and runtime still serve published bundles |
| Native C prototypes and test drivers | 501 lines of retained prototype/driver translation units; never enabled by the native installation builder |
| Native build and test tools | 3,188 lines of Python/Zsh under `native`, including focused regression and measurement harnesses |
| Development artifact assembly | Existing Rust manager verifies the manifest; private duplicate `bin/zsh` remains alongside `bin/wsh`; no manager executable is installed in the native payload |
| Installation and updates | RPM/DNF owns system files, registration and transactions; native startup has no self-update/activation authority |
| Terminal restore | Wakterm's actual caller uses native exact-argv foreground invocation for the packaged paths; generic shells and the legacy launcher retain their existing path |

The qualified host payload has 1,275 regular files totaling 9,871,975 bytes, including generated `.zwc` files, upstream autoload functions, documentation and the duplicate executable. Its shell is 1,864,824 bytes and helper 372,320 bytes. The floor payload has its own recorded manifest and ELF dependencies. Removing the duplicate shell saves one executable only after changing the shared development artifact contract; no such deletion is claimed here.

## Counting method

`responsibility-inventory.json` lists each counted path, hash, byte count and physical line count, including blank lines and comments. Categories distinguish production additions, retained tests/prototypes, third-party source and legacy consumers. They are not a performance score or a like-for-like C/Rust size claim. The downloaded upstream Zsh tree and system shared-library implementations remain external maintained dependencies, identified by the native source lock, ELF requirements and SDK package records. Generated installed files are counted in the complete payload manifest, rather than counted as hand-written source.

## Decisions retained for discussion

| Decision | Evidence and smallest next step |
|---|---|
| Publish native system packages | Approve a package name, signing/distribution contract and locked canonical builder extension. Local floor builds, identical RPMs and VM tests pass; publication is not authorized |
| Supported account directories and incompatible upgrades | The local account removal guard is tested. Decide remote-directory/alias support and the policy for incompatible external modules, autoload functions or helper protocols before claiming broader support |
| Retire the legacy distribution and shared manifest assembler | Keep published-installation update/rollback and exceptional saved-report support until consumers migrate. Then remove the unused Rust crates/toolchain, duplicate private shell and legacy artifact schema together |
| Adopt focused directory/history/suggestion kernels | Focused parity and timing comparisons pass. Each is a partial internal port; broader ZLE/composition and maintenance tradeoffs still need an adoption decision. The full pinned plugins remain selected |
| Completion initialization | Valid read-only seed improves the measured path, but stale/unusable fallback misses the startup gate. Keep current initialization; retain the experiment for a new hypothesis |
| Highlight classification | Full redraw gains fail the fixed adoption gates. Keep the existing implementation |

Direct runtime embedding is rejected by the observed child-ownership failures; the helper remains selected. Cross-shell collection remains deferred until measurements justify it. Prompt rendering and shell lifecycle stay local. No new provider framework, broker, database or activation mechanism was added.
