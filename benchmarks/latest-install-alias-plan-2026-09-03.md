# Stable latest-installer URL experiment

The install command currently embeds the release version twice. GitHub resolves `https://github.com/wakamex/wsh/releases/latest/download/wsh-install.sh` to the current immutable release, but the request returns HTTP 404 because `v0.1.3` publishes only `wsh-v0.1.3-install.sh`.

The smallest counterfactual is a second asset name for the same generated bootstrap. The publisher will copy the already byte-compared release-specific bootstrap to `wsh-install.sh` before generating checksums and attestations. It will not introduce a mutable branch-hosted installer, a second script implementation, or another installation protocol.

The intervention passes when the release workflow proves that `wsh-install.sh` is byte-identical to the release-specific bootstrap, includes it in `SHA256SUMS` and workflow build provenance, publishes both names in the same immutable release, and verifies the published alias with every other asset. After the next release, the latest-release URL must return that release's exact bootstrap and a fresh isolated installation through the general command must pass the existing install gates.

Make one workflow-only attempt. If the alias cannot remain an attested byte-for-byte copy inside the immutable release, stop and retain the versioned installation URL rather than adding a redirect service or branch-hosted script.
