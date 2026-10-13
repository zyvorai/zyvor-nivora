// SPDX-License-Identifier: BUSL-1.1
import SwiftUI
import AppKit

extension Color {
    /// `#rrggbb`
    init(hex: String) {
        var h = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        if h.count == 3 { h = h.map { "\($0)\($0)" }.joined() }
        let v = UInt64(h, radix: 16) ?? 0
        self.init(.sRGB, red: Double((v >> 16) & 0xFF) / 255, green: Double((v >> 8) & 0xFF) / 255, blue: Double(v & 0xFF) / 255, opacity: 1)
    }

    /// Adapts to light/dark appearance.
    init(light: String, dark: String) {
        self = Color(nsColor: NSColor(name: nil) { appearance in
            let isDark = appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            return NSColor(Color(hex: isDark ? dark : light))
        })
    }
}

/// Netra palette (../netra/web/src/styles.css), mirrored by the web tokens in web/styles.css.
/// tests/test_native_contract.py asserts these hex values stay equal to the web tokens.
enum Palette {
    static let page = Color(light: "#ffffff", dark: "#000000")
    static let panel = Color(light: "#f5f5f7", dark: "#1d1d1f")
    static let raised = Color(light: "#ffffff", dark: "#2c2c2e")
    static let textPrimary = Color(light: "#1d1d1f", dark: "#f5f5f7")
    static let textSecondary = Color(light: "#6e6e73", dark: "#a1a1a6")
    static let textTertiary = Color(light: "#86868b", dark: "#86868b")
    static let hairline = Color(light: "#d2d2d7", dark: "#3a3a3c")
    static let accent = Color(light: "#0071e3", dark: "#2997ff")
    static let cyan = Color(light: "#32ade6", dark: "#64d2ff")
    static let green = Color(light: "#34c759", dark: "#30d158")
    static let amber = Color(light: "#ff9f0a", dark: "#ff9f0a")
    static let purple = Color(light: "#af52de", dark: "#bf5af2")
    static let danger = Color(light: "#ff3b30", dark: "#ff453a")

    static func status(_ s: String) -> Color {
        switch s.lowercased() {
        case "healthy", "good", "active", "established", "loopback": return green
        case "degraded", "warning", "medium", "all": return amber
        case "poor", "critical", "high": return danger
        default: return textSecondary
        }
    }
}

extension View {
    /// Netra heading: semibold, slightly tightened.
    func netraTitle(_ size: CGFloat = 17) -> some View {
        font(.system(size: size, weight: .semibold)).tracking(-0.2).foregroundStyle(Palette.textPrimary)
    }
    func caption2Style() -> some View { font(.caption).foregroundStyle(Palette.textSecondary) }
}
