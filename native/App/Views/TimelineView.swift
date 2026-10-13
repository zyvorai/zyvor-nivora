// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

/// Network Time Machine: interface, DNS, route, VPN, listener and capture events, newest first.
struct TimelineView: View {
    @EnvironmentObject var store: NivoraStore
    @State private var kind: String?

    var body: some View {
        let all = store.timeline
        let events = TimelineKit.filter(all, kind: kind, query: store.search)
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                Picker("Kind", selection: $kind) {
                    Text("All events").tag(String?.none)
                    ForEach(TimelineKit.kinds(all), id: \.self) { Text($0.capitalized).tag(Optional($0)) }
                }
                .pickerStyle(.menu).fixedSize()
                Spacer()
                Text(kind == nil && store.search.isEmpty ? "\(all.count) events" : "\(events.count) of \(all.count)")
                    .font(.caption).monospacedDigit().foregroundStyle(Palette.textSecondary)
            }
            .padding(.horizontal, 16).padding(.vertical, 8)
            .background(.bar)
            Divider()
            if events.isEmpty {
                ContentUnavailableView {
                    Label("No events", systemImage: "clock.arrow.circlepath")
                } description: {
                    Text(all.isEmpty ? "Nothing has changed since Nivora started watching." : "No events match this filter.")
                } actions: {
                    if kind != nil || !store.search.isEmpty { Button("Clear filter") { kind = nil; store.search = "" } }
                }
            } else {
                List {
                    ForEach(TimelineKit.byDay(events)) { day in
                        Section(day.id) {
                            ForEach(day.events) { e in
                                HStack(alignment: .top, spacing: 12) {
                                    Image(systemName: TimelineKit.symbol(for: e.kind))
                                        .frame(width: 24).foregroundStyle(Palette.accent)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(e.title).font(.callout.weight(.medium))
                                        if let d = e.detail, !d.isEmpty { Text(d).font(.caption).foregroundStyle(Palette.textSecondary) }
                                    }
                                    Spacer()
                                    Text(String(e.ts.dropFirst(11).prefix(8))).font(.caption).monospacedDigit().foregroundStyle(Palette.textTertiary)
                                }
                                .padding(.vertical, 2)
                            }
                        }
                    }
                }
            }
        }
        .task {
            while !Task.isCancelled {
                await store.refreshTimeline()
                try? await Task.sleep(for: .seconds(3))
            }
        }
    }
}
