# Releasing

1. Bump `package.json`, `agent/nivora_core.py` `VERSION`, `native/project.yml` `MARKETING_VERSION` and the changelog; run `./scripts/test.sh`.
2. Tag `vX.Y.Z` and push. `release.yml` builds an **unsigned (ad-hoc sealed)** DMG, an SBOM, a build-provenance attestation and a version-synced `nivora.rb`, and drafts the GitHub release.
3. The **notarized** DMG is the paid build (see the README's licence section), so it is delivered to paying customers and is **not** uploaded to the public GitHub release or used by the Homebrew cask, which both stay on the free unsigned DMG. To produce it, build locally and sign on the Mac mini (or run `scripts/package-signed.sh` directly on a Mac that holds the certificate; `notarize-mini.sh` is the same build driven over ssh):

   ```bash
   ./scripts/build-native.sh
   ./scripts/notarize-mini.sh --dry-run     # review what will run
   ./scripts/notarize-mini.sh               # add --gui if codesign hits a keychain error over ssh
   ```

   It signs with the Developer ID Application identity and the hardened runtime, notarizes and staples the app itself, then builds the DMG and submits it with the `Macora-Notary` keychain profile (the app's own ticket lets it pass Gatekeeper offline after it is dragged out of the DMG), staples, checks with `spctl` and writes `Nivora-X.Y.Z.dmg` and its `.sha256`. Keep them with the other paid builds and send the DMG to buyers; leave the public release and `nivora.rb` on the unsigned DMG and its checksum (`python3 scripts/update-cask.py SHA256SUMS.txt` from the release assets).
4. The notarized app leaves out the content filter, capture helper and its launchd plist (they need the NetworkExtension entitlement and a provisioning profile; a plain Developer ID signature would stop macOS launching the app). Those still need a provisioned build. See `docs/NETWORKEXTENSION.md`.

## Pages

`pages.yml` runs on GitHub-hosted `ubuntu-latest`. To deploy from the self-hosted Mac mini, set the repository variable `PAGES_RUNNER` to `["self-hosted","mini"]`; delete it to go back.
