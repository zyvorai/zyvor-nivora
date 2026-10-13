// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

/// Chips for the active filter, one-click quick filters, saved views and a "N of M" count.
/// Shared by the Flows and Applications panes; the grammar is `FlowFilter` (same as the collector and web UI).
struct FilterBar: View {
    @EnvironmentObject var store: NivoraStore
    let shown: Int
    let total: Int
    var noun = "flows"

    private var chips: [String] { FlowFilter.chips(store.search) }

    private var quick: [String] {
        guard let s = store.snapshot else { return [] }
        var out: [String] = []
        if let top = s.apps.max(by: { $0.total_bps < $1.total_bps })?.name {
            out.append(top.contains(" ") ? "app:\"\(top)\"" : "app:\(top)")
        }
        out += ["proto:tcp", "proto:udp", "port:443", ">1mbps"]
        out += Array(Set(s.flows.map(\.interface).filter { !$0.isEmpty })).sorted().prefix(2).map { "iface:\($0)" }
        let active = Set(chips)
        return out.filter { !active.contains($0.replacingOccurrences(of: "\"", with: "")) }.prefix(6).map { $0 }
    }

    var body: some View {
        HStack(spacing: 8) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(Array(chips.enumerated()), id: \.offset) { i, chip in
                        Button { store.search = FlowFilter.dropChip(store.search, at: i) } label: {
                            HStack(spacing: 4) { Text(chip); Image(systemName: "xmark").font(.system(size: 8, weight: .bold)) }
                                .font(.caption.weight(.medium))
                                .padding(.horizontal, 9).padding(.vertical, 3)
                                .foregroundStyle(Palette.accent)
                                .background(Palette.accent.opacity(0.12), in: Capsule())
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("Remove filter \(chip)")
                    }
                    ForEach(quick, id: \.self) { q in
                        Button { store.search = (store.search.trimmingCharacters(in: .whitespaces) + " " + q).trimmingCharacters(in: .whitespaces) } label: {
                            Text("+ \(q)").font(.caption)
                                .padding(.horizontal, 9).padding(.vertical, 3)
                                .foregroundStyle(Palette.textSecondary)
                                .overlay(Capsule().strokeBorder(Palette.hairline, style: StrokeStyle(lineWidth: 1, dash: [3, 2])))
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            Spacer(minLength: 8)
            Text(chips.isEmpty ? "\(total) \(noun)" : "\(shown) of \(total)")
                .font(.caption).monospacedDigit().foregroundStyle(Palette.textSecondary)
            Menu {
                ForEach(store.savedViews) { v in Button(v.name) { store.apply(v) } }
                if !store.savedViews.isEmpty { Divider() }
                Button("Save current filter") { store.saveCurrentView() }.disabled(chips.isEmpty)
                Menu("Delete view") {
                    ForEach(store.savedViews) { v in Button(v.name, role: .destructive) { store.deleteView(v) } }
                }.disabled(store.savedViews.isEmpty)
                if !chips.isEmpty { Divider(); Button("Clear filter") { store.search = "" } }
            } label: { Label("Views", systemImage: "line.3.horizontal.decrease.circle") }
            .menuStyle(.borderlessButton).fixedSize()
        }
        .padding(.horizontal, 16).padding(.vertical, 8)
        .background(.bar)
    }
}

/// Empty state that offers the obvious next step instead of a dead end.
struct FilteredEmpty: View {
    @EnvironmentObject var store: NivoraStore
    let title: String
    let symbol: String
    let idle: String

    var body: some View {
        let filtering = !store.search.trimmingCharacters(in: .whitespaces).isEmpty
        ContentUnavailableView {
            Label(title, systemImage: symbol)
        } description: {
            Text(filtering ? "Nothing matches “\(store.search)”." : idle)
        } actions: {
            if filtering { Button("Clear filter") { store.search = "" } }
        }
    }
}

/// Compact "what changed since the baseline" card for the Flows pane.
struct BaselineCard: View {
    @EnvironmentObject var store: NivoraStore

    var body: some View {
        if let base = store.baseline, let now = store.snapshot?.flows {
            let d = FlowDiff.compare(before: base.flows, after: now)
            Panel(title: "Changes since \(base.time.formatted(date: .omitted, time: .standard))") {
                HStack(spacing: 24) {
                    tile("New", d.added.count)
                    tile("Gone", d.removed.count)
                    tile("Rate moves", d.changed.count)
                    Spacer()
                    Button("Clear") { store.clearBaseline() }
                }
                ForEach(d.added.prefix(4)) { row($0, "new") }
                ForEach(d.removed.prefix(4)) { row($0, "gone") }
                ForEach(Array(d.changed.prefix(5)), id: \.flow.id) { c in
                    row(c.flow, (c.delta > 0 ? "+" : "−") + rateString(abs(c.delta)))
                }
            }
        }
    }

    private func tile(_ label: String, _ n: Int) -> some View {
        VStack(alignment: .leading) {
            Text("\(n)").font(.system(size: 20, weight: .semibold)).monospacedDigit()
            Text(label).font(.caption).foregroundStyle(Palette.textSecondary)
        }
    }

    private func row(_ f: NivoraSnapshot.Flow, _ tag: String) -> some View {
        HStack {
            Text(f.process).fontWeight(.medium)
            Text(f.remote).font(.system(.callout, design: .monospaced)).foregroundStyle(Palette.textSecondary)
            Spacer()
            Text(tag).monospacedDigit().foregroundStyle(Palette.textSecondary)
        }
    }
}
