# Release-mode package reproducibility and fresh Fedora QEMU qualification

Qualify commit 13cb60dcc0ff28d8d49ca55de30e831f98d3801d before release selection. Build two clean detached worktrees with WSH_BUNDLE_STATUS=release through the canonical Rocky Linux 8.10/glibc 2.28 SDK. Both canonical suites must pass; native manifests and RPM bytes must match exactly. These are unsigned local qualification artifacts, not an official release.

Then install one agreed RPM in a fresh overlay of the previously signature-verified Fedora 44 cloud image. Use QEMU/KVM, SELinux enforcing, and an independent recovery account. Require installed version and inventory agreement, actual serial-getty/PAM login with empty per-user state, native prompt readiness and job control, legacy launcher PATH migration with preserved user files, unavailable legacy activation state and optional-resource recovery, authenticated chsh, and successful login after reboot. Preserve exact commands, output, artifacts and hashes. No host account-shell or installation changes, push, tag or release is part of this qualification.

If a gate fails, retain the failing worker or VM and attribute the failure before changing code. After two failed interventions at a gate, audit the premise before another attempt. Timing here is not a performance comparison.
