# Releasing

1. Bump `package.json`, `agent/nivora_core.py` `VERSION`, `native/project.yml` `MARKETING_VERSION` and the changelog; run `./scripts/test.sh`.
2. Tag `vX.Y.Z` and push. `release.yml` builds an **unsigned (ad-hoc sealed)** DMG, an SBOM, a build-provenance attestation and a version-synced `nivora.rb`, and drafts the GitHub release.
3. To ship a **notarized** DMG instead, build locally and sign on the Mac mini:

   ```bash
   ./scripts/build-native.sh
   ./scripts/notarize-mini.sh --dry-run     # review what will run
   ./scripts/notarize-mini.sh               # add --gui if codesign hits a keychain error over ssh
   ```

   It signs with the Developer ID Application identity and the hardened runtime, submits with the `Macora-Notary` keychain profile, staples, checks with `spctl` and writes `Nivora-X.Y.Z.dmg` and its `.sha256`. Upload those to the draft release in place of the unsigned DMG and update the cask (`python3 scripts/update-cask.py Nivora-X.Y.Z.dmg.sha256`), removing its Gatekeeper caveat once the release is notarized.
4. The notarized app is signed without the NetworkExtension entitlements (they need a provisioning profile), so the content filter and capture helper still need a provisioned build. See `docs/NETWORKEXTENSION.md`.

## Pages

`pages.yml` runs on GitHub-hosted `ubuntu-latest`. To deploy from the self-hosted Mac mini, set the repository variable `PAGES_RUNNER` to `["self-hosted","mini"]`; delete it to go back.
