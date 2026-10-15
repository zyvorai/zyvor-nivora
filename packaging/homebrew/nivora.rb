# SPDX-License-Identifier: BUSL-1.1
# Draft cask for the zyvorai/homebrew-tap repository (Casks/nivora.rb).
# UNVERIFIED: not installed through Homebrew. Before publishing, set `version` to a published release and
# replace `sha256` with the value from that release's SHA256SUMS.txt. The DMG is unsigned and not notarised,
# so Gatekeeper still asks for "Open Anyway" (see docs/INSTALL.md).
cask "nivora" do
  version "0.3.0"
  sha256  "REPLACE_WITH_SHA256_FROM_SHA256SUMS_TXT"

  url "https://github.com/zyvorai/zyvor-nivora/releases/download/v#{version}/Nivora-#{version}.dmg"
  name "Nivora"
  desc "Mac-native application and network intelligence, observe-first"
  homepage "https://zyvorai.github.io/zyvor-nivora/"

  depends_on macos: :sonoma

  app "Nivora.app"

  zap trash: [
    "~/.local/share/nivora",
    "~/Library/Group Containers/group.dev.zyvor.nivora",
  ]
end
