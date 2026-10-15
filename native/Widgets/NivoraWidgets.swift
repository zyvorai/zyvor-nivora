// SPDX-License-Identifier: BUSL-1.1
import SwiftUI
import WidgetKit

struct NivoraEntry: TimelineEntry {
    let date: Date
    let data: WidgetData?
}

struct NivoraProvider: TimelineProvider {
    func placeholder(in context: Context) -> NivoraEntry { NivoraEntry(date: Date(), data: Self.sample) }
    func getSnapshot(in context: Context, completion: @escaping (NivoraEntry) -> Void) {
        completion(NivoraEntry(date: Date(), data: context.isPreview ? Self.sample : WidgetStore.read()))
    }
    func getTimeline(in context: Context, completion: @escaping (Timeline<NivoraEntry>) -> Void) {
        let now = Date()
        completion(Timeline(entries: [NivoraEntry(date: now, data: WidgetStore.read())], policy: .after(now.addingTimeInterval(60))))
    }
    /// Gallery preview only; never shown as a reading.
    static let sample = WidgetData(updated: Date(), host: "zyvor-mac-studio", simulated: true, health: 92, download: 3.4e6, upload: 0.8e6,
                                   flows: 8, findings: 1, topApps: [.init(name: "Google Chrome", bps: 1.9e6), .init(name: "Xcode", bps: 7.7e5), .init(name: "Slack", bps: 1.4e5)])
}

private func rate(_ v: Double) -> String {
    let f = ByteCountFormatter(); f.countStyle = .file; f.allowsNonnumericFormatting = false
    return f.string(fromByteCount: Int64(max(0, v))) + "/s"
}

private struct HealthRing: View {
    let value: Int
    var body: some View {
        ZStack {
            Circle().stroke(.quaternary, lineWidth: 7)
            Circle().trim(from: 0, to: min(1, max(0, Double(value) / 100)))
                .stroke(value >= 85 ? Color.green : value >= 60 ? Color.orange : Color.red, style: StrokeStyle(lineWidth: 7, lineCap: .round))
                .rotationEffect(.degrees(-90))
            VStack(spacing: 0) {
                Text("\(value)").font(.system(.title3, design: .rounded).weight(.semibold)).monospacedDigit()
                Text("health").font(.caption2).foregroundStyle(.secondary)
            }
        }
        .frame(width: 70, height: 70)
    }
}

struct NivoraWidgetView: View {
    @Environment(\.widgetFamily) private var family
    let entry: NivoraEntry

    var body: some View {
        Group {
            if let d = entry.data {
                if family == .systemSmall { small(d) } else { medium(d) }
            } else {
                VStack(spacing: 6) {
                    Image(systemName: "network").font(.title2).foregroundStyle(.secondary)
                    Text("Open Nivora to start readings").font(.caption).multilineTextAlignment(.center).foregroundStyle(.secondary)
                }
            }
        }
        .containerBackground(.background, for: .widget)
    }

    private func footer(_ d: WidgetData) -> some View {
        let text = d.simulated ? "Simulated" : d.isStale(now: entry.date) ? "Nivora is not running · \(d.age(now: entry.date))" : d.host
        return Text(text).font(.caption2).foregroundStyle(.secondary).lineLimit(1)
    }

    private func small(_ d: WidgetData) -> some View {
        VStack(spacing: 6) {
            HealthRing(value: d.health)
            Text("↓ \(rate(d.download))  ↑ \(rate(d.upload))").font(.caption2).monospacedDigit().lineLimit(1).minimumScaleFactor(0.7)
            footer(d)
        }
    }

    private func medium(_ d: WidgetData) -> some View {
        HStack(alignment: .top, spacing: 16) {
            VStack(spacing: 6) { HealthRing(value: d.health); footer(d) }.frame(width: 120)
            VStack(alignment: .leading, spacing: 6) {
                Text("↓ \(rate(d.download))   ↑ \(rate(d.upload))").font(.caption.weight(.semibold)).monospacedDigit()
                ForEach(Array(d.topApps.prefix(3).enumerated()), id: \.offset) { _, app in
                    HStack { Text(app.name).lineLimit(1); Spacer(); Text(rate(app.bps)).monospacedDigit().foregroundStyle(.secondary) }.font(.callout)
                }
                if d.topApps.isEmpty { Text("No app data").font(.callout).foregroundStyle(.secondary) }
                Spacer(minLength: 0)
                if d.findings > 0 {
                    Label("\(d.findings) finding\(d.findings == 1 ? "" : "s")", systemImage: "exclamationmark.triangle.fill")
                        .font(.caption).foregroundStyle(.orange)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
    }
}

struct NivoraStatusWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "dev.zyvor.nivora.status", provider: NivoraProvider()) { entry in
            NivoraWidgetView(entry: entry)
        }
        .configurationDisplayName("Network")
        .description("Health, live rates and the busiest apps. Read-only; readings come from the Nivora app.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

@main
struct NivoraWidgetBundle: WidgetBundle {
    var body: some Widget { NivoraStatusWidget() }
}
