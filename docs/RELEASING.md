# Releasing

1. Bump `package.json`, `agent/nivora_core.py` `VERSION`, `native/project.yml` `MARKETING_VERSION` and the changelog; run `./scripts/test.sh`.
2. Tag `vX.Y.Z` and push. `release.yml` builds an **unsigned (ad-hoc sealed)** DMG, an SBOM, a build-provenance attestation and a version-synced `nivora.rb`, and drafts the GitHub release.
3. To ship a **notarized** DMG instead, build locally and sign on the Mac mini (or run `scripts/package-signed.sh` directly on a Mac that holds the certificate; `notarize-mini.sh` is the same build driven over ssh):

   ```bash
   ./scripts/build-native.sh
   ./scripts/notarize-mini.sh --dry-run     # review what will run
   ./scripts/notarize-mini.sh               # add --gui if codesign hits a keychain error over ssh
   ```

   It signs with the Developer ID Application identity and the hardened runtime, notarizes and staples the app itself, then builds the DMG and submits it with the `Macora-Notary` keychain profile (the app's own ticket lets it pass Gatekeeper offline after it is dragged out of the DMG), staples, checks with `spctl` and writes `Nivora-X.Y.Z.dmg` and its `.sha256`. Upload those to the draft release in place of the unsigned DMG and update the cask (`python3 scripts/update-cask.py Nivora-X.Y.Z.dmg.sha256`), removing its Gatekeeper caveat once the release is notarized.
4. The notarized app leaves out the content filter, capture helper and its launchd plist (they need the NetworkExtension entitlement and a provisioning profile; a plain Developer ID signature would stop macOS launching the app). Those still need a provisioned build. See `docs/NETWORKEXTENSION.md`.

## Pages

`pages.yml` runs on GitHub-hosted `ubuntu-latest`. To deploy from the self-hosted Mac mini, set the repository variable `PAGES_RUNNER` to `["self-hosted","mini"]`; delete it to go back.
