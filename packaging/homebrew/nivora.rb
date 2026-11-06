# SPDX-License-Identifier: BUSL-1.1
# Cask for the zyvorai/homebrew-tap repository (Casks/nivora.rb); keep in sync with the tap.
# On each release set `version` and `sha256` (from that release's SHA256SUMS.txt) here and in the tap.
# UNVERIFIED: not installed through Homebrew. The DMG is unsigned and not notarised, so Gatekeeper still
# asks for "Open Anyway" (see docs/INSTALL.md).
cask "nivora" do
  version "0.5.2"
  sha256  "9ee24b4386c78d97e6f34fb878341e7e9dca3e775d7c2df2895bd6de0eeba99d"

  url "https://github.com/zyvorai/zyvor-nivora/releases/download/v#{version}/Nivora-#{version}.dmg"
  name "Nivora"
  desc "Mac-native application and network intelligence, observe-first"
  homepage "https://zyvorai.github.io/zyvor-nivora/"

  depends_on macos: :sonoma
  depends_on arch: :arm64

  app "Nivora.app"

  caveats <<~EOS
    This build is unsigned and not notarised. On first launch macOS will block it:
    open System Settings > Privacy & Security and choose "Open Anyway" next to Nivora.
    See https://github.com/zyvorai/zyvor-nivora/blob/main/docs/INSTALL.md
  EOS

  zap trash: [
    "~/.local/share/nivora",
    "~/Library/Group Containers/group.dev.zyvor.nivora",
  ]
end
