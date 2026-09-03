# v0.1.2 public update failure

The public `v0.1.2` installer could perform a fresh installation but could not update an existing `v0.1.1` installation. An isolated Fedora 44 test installed `v0.1.1`, ran the exact `v0.1.2` GitHub Release bootstrap against the same bin, libexec, and state roots, and received `error: SHA-256 mismatch for wsh`. The active `v0.1.1` bundle remained selected and intact.

The failing releases were [`v0.1.1`](https://github.com/wakamex/wsh/releases/tag/v0.1.1) at source commit `e62e19fe1cf8b10d28b703e2670b6478e540f38d` and [`v0.1.2`](https://github.com/wakamex/wsh/releases/tag/v0.1.2) at source commit `eaab8858b5cbbb96e6782a3d0fa127f690dad390`. The test used private temporary `HOME`, `WSH_BIN_DIR`, `WSH_LIBEXEC_DIR`, and `WSH_STATE_ROOT` directories and fetched both release-specific bootstrap scripts over HTTPS.

The bootstrap verified that an existing launcher and installer already matched the new release's embedded digests. That condition made rerunning one release idempotent but classified every legitimate cross-version tool change as corruption. The failure occurred before replacement or candidate execution, which preserved the active bundle but made the documented update path unusable.

The corrective experiment and fixed acceptance gates are recorded in [`public-update-v0.1.3-plan-2026-09-03.md`](public-update-v0.1.3-plan-2026-09-03.md).
