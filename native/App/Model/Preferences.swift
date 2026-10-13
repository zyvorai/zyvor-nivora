// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

/// Accents shared with the web dashboard (ACCENTS in web/lib.js; Netra palette).
enum AccentChoice: String, CaseIterable, Identifiable {
    case blue, cyan, green, amber, purple, graphite
    var id: Self { self }
    var label: String { rawValue.capitalized }
    var color: Color {
        switch self {
        case .blue: return Color(hex: "#0071e3")
        case .cyan: return Color(hex: "#32ade6")
        case .green: return Color(hex: "#34c759")
        case .amber: return Color(hex: "#ff9f0a")
        case .purple: return Color(hex: "#af52de")
        case .graphite: return Color(hex: "#6e6e73")
        }
    }
}

enum AppearanceChoice: String, CaseIterable, Identifiable {
    case auto, light, dark
    var id: Self { self }
    var label: String { rawValue.capitalized }
    var scheme: ColorScheme? { self == .light ? .light : self == .dark ? .dark : nil }
}
