// SPDX-License-Identifier: BUSL-1.1
import SwiftUI
import Charts

/// A flat grouped surface (Vytrix `Panel`), coloured with the Netra palette.
struct Panel<Content: View>: View {
    var title: String?
    var subtitle: String?
    @ViewBuilder var content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let title {
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).netraTitle()
                    if let subtitle { Text(subtitle).font(.callout).foregroundStyle(Palette.textSecondary) }
                }
            }
            content
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Palette.panel, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(Palette.hairline.opacity(0.5), lineWidth: 0.5))
    }
}

struct MetricTile: View {
    let label: String
    let symbol: String
    let value: String
    var unit: String = ""
    let hint: String
    var series: [Double] = []
    var tint: Color = Palette.accent
    var action: (() -> Void)?

    var body: some View {
        Button { action?() } label: {
            VStack(alignment: .leading, spacing: 10) {
                Label(label, systemImage: symbol).font(.callout.weight(.medium)).foregroundStyle(Palette.textSecondary)
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(value).font(.system(size: 26, weight: .semibold)).tracking(-0.4).monospacedDigit().foregroundStyle(Palette.textPrimary)
                    Text(unit).font(.callout).foregroundStyle(Palette.textTertiary)
                }
                Text(hint).font(.caption).foregroundStyle(Palette.textSecondary).lineLimit(1)
                if series.count > 1 {
                    Chart(Array(series.enumerated()), id: \.offset) { LineMark(x: .value("t", $0.offset), y: .value("v", $0.element)) }
                        .chartXAxis(.hidden).chartYAxis(.hidden)
                        .foregroundStyle(tint)
                        .frame(height: 30)
                } else {
                    Spacer().frame(height: 30)
                }
            }
            .padding(18)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Palette.panel, in: RoundedRectangle(cornerRadius: 14))
            .contentShape(RoundedRectangle(cornerRadius: 14))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(label): \(value) \(unit)")
    }
}

/// A thin horizontal bar, 0...1.
struct Meter: View {
    let fraction: Double
    var tint: Color = Palette.accent
    var body: some View {
        GeometryReader { g in
            ZStack(alignment: .leading) {
                Capsule().fill(Palette.hairline.opacity(0.6))
                Capsule().fill(tint).frame(width: max(2, g.size.width * min(1, max(0, fraction))))
            }
        }
        .frame(height: 5)
    }
}

/// Neutral monogram, the app-icon stand-in (no per-app colours).
struct Monogram: View {
    let name: String
    var size: CGFloat = 28
    var body: some View {
        Text(String(name.prefix(1)).uppercased())
            .font(.system(size: size * 0.46, weight: .semibold))
            .foregroundStyle(Palette.textSecondary)
            .frame(width: size, height: size)
            .background(Palette.hairline.opacity(0.45), in: RoundedRectangle(cornerRadius: size * 0.26))
    }
}

struct StatusPill: View {
    let text: String
    var kind: String?
    var body: some View {
        let c = Palette.status(kind ?? text)
        Text(text).font(.caption.weight(.medium))
            .padding(.horizontal, 8).padding(.vertical, 2)
            .foregroundStyle(c)
            .background(c.opacity(0.14), in: Capsule())
    }
}

struct Page<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        ScrollView { VStack(alignment: .leading, spacing: 16) { content }.padding(24) }
            .background(Palette.page)
    }
}

struct RateChart: View {
    let samples: [Sample]
    var body: some View {
        Chart {
            ForEach(samples) { s in
                AreaMark(x: .value("Time", s.time), y: .value("Download", s.rx), series: .value("k", "Download"))
                    .foregroundStyle(Palette.accent.opacity(0.18))
                LineMark(x: .value("Time", s.time), y: .value("Download", s.rx), series: .value("k", "Download"))
                    .foregroundStyle(Palette.accent)
                LineMark(x: .value("Time", s.time), y: .value("Upload", s.tx), series: .value("k", "Upload"))
                    .foregroundStyle(Palette.purple)
            }
        }
        .chartYAxis { AxisMarks { v in AxisGridLine(); AxisValueLabel { if let d = v.as(Double.self) { Text(rateString(d)) } } } }
        .frame(height: 180)
    }
}
