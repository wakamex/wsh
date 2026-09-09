# Native installations select the tested C helper

The native assembler now builds and installs the complete C runtime directly. Two builds in different directories and the installed helper have the same SHA-256 digest. The assembled installation passes all nine component contracts, including real Oh My Zsh coexistence and foreground job control. The helper passes 2,237 protocol decoder cases, 400 complete prompt/snapshot comparisons and 15 lifecycle, trace and cleanup cases.

This selects the implementation already qualified by the [full runtime comparison](../native-render-2026-09-08/runtime-report.md), with source/output paths normalized in diagnostic strings. No runtime behavior changes. Native payloads include the parser licenses, locked native inputs and effective linked-module configuration. The legacy distribution retains its Rust runtime and manager; native assembly still uses the manager to verify the development manifest.

The [plan](runtime-plan.md) fixes the gates. `runtime-metadata.json` identifies commands, source inputs and binary hashes; the input and result archives retain their bytes. Full floor builds and package migration are separate qualification stages. These are unsigned development artifacts.
