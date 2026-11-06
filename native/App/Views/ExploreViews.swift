// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

/// Applications → interfaces → destinations, drawn from the collector's `topology`.
struct NetworkMapView: View {
    @EnvironmentObject var store: NivoraStore
    private let rowHeight: CGFloat = 36

    var body: some View {
        if let t = store.snapshot?.topology {
            let layout = MapLayout.make(t)
            Page {
                Panel(title: "Network map", subtitle: "Busiest applications, the interface they use and where they connect. Line weight is live traffic.") {
                    if layout.rows == 0 {
                        Text("No traffic to map yet.").foregroundStyle(Palette.textSecondary)
                    } else {
                        MapCanvas(layout: layout, rowHeight: rowHeight)
                            .frame(height: CGFloat(layout.rows) * rowHeight)
                    }
                }
            }
        } else {
            ContentUnavailableView("No topology", systemImage: "point.3.connected.trianglepath.dotted",
                                   description: Text("This collector did not report a topology."))
        }
    }
}

private struct MapCanvas: View {
    let layout: MapLayout
    let rowHeight: CGFloat

    var body: some View {
        GeometryReader { geo in
            let chip = min(230, geo.size.width * 0.28)
            let xs: [CGFloat] = [0, (geo.size.width - chip) / 2, geo.size.width - chip]
            ZStack(alignment: .topLeading) {
                Canvas { ctx, _ in
                    for e in layout.links {
                        guard let a = layout.position(of: e.source), let b = layout.position(of: e.target) else { continue }
                        let p0 = CGPoint(x: xs[a.column] + chip, y: CGFloat(a.row) * rowHeight + rowHeight / 2)
                        let p1 = CGPoint(x: xs[b.column], y: CGFloat(b.row) * rowHeight + rowHeight / 2)
                        var path = Path()
                        path.move(to: p0)
                        let dx = (p1.x - p0.x) / 2
                        path.addCurve(to: p1, control1: CGPoint(x: p0.x + dx, y: p0.y), control2: CGPoint(x: p1.x - dx, y: p1.y))
                        ctx.stroke(path, with: .color(Palette.accent.opacity(0.35)),
                                   lineWidth: 1 + 5 * CGFloat(e.bps / layout.maxBps))
                    }
                }
                .accessibilityHidden(true)
                column(layout.apps, x: xs[0], width: chip)
                column(layout.interfaces, x: xs[1], width: chip)
                column(layout.destinations, x: xs[2], width: chip)
            }
        }
    }

    private func column(_ nodes: [NivoraSnapshot.Topology.Node], x: CGFloat, width: CGFloat) -> some View {
        ForEach(Array(nodes.enumerated()), id: \.element.id) { row, n in
            Text(n.label).font(.callout).lineLimit(1).truncationMode(.middle)
                .padding(.horizontal, 10).frame(width: width, height: rowHeight - 8, alignment: .leading)
                .background(Palette.raised, in: RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Palette.hairline.opacity(0.6), lineWidth: 0.5))
                .offset(x: x, y: CGFloat(row) * rowHeight + 4)
                .accessibilityLabel("\(n.kind) \(n.label)")
        }
    }
}

struct DomainsView: View {
    @EnvironmentObject var store: NivoraStore
    var body: some View {
        let rows = DomainSummary.make(from: store.flows)
        Table(rows) {
            TableColumn("Host") { Text($0.host).font(.system(.callout, design: .monospaced)) }
            TableColumn("Applications") { Text($0.apps.prefix(3).joined(separator: ", ")) }
            TableColumn("Flows") { Text("\($0.flows)").monospacedDigit() }
            TableColumn("Ports") { Text($0.ports.isEmpty ? "—" : $0.ports.map(String.init).joined(separator: ", ")).monospacedDigit() }
            TableColumn("Traffic") { Text(byteString($0.bytes)).monospacedDigit() }
        }
        .overlay { if rows.isEmpty { ContentUnavailableView("No destinations", systemImage: "globe", description: Text(store.search.isEmpty ? "No flows yet." : "No flow matches this filter.")) } }
    }
}

struct DNSView: View {
    @EnvironmentObject var store: NivoraStore
    var body: some View {
        if let s = store.snapshot {
            let resolvers = s.dns.resolvers ?? []
            Page {
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: 3), spacing: 12) {
                    MetricTile(label: "Resolvers", symbol: "server.rack", value: "\(resolvers.count)", hint: "from scutil")
                    MetricTile(label: "Nameservers", symbol: "number", value: "\(s.dns.servers.count)", hint: s.dns.servers.joined(separator: " · "))
                    MetricTile(label: "Search domains", symbol: "magnifyingglass", value: "\(Set(resolvers.flatMap { $0.search ?? [] }).count)", hint: "configured")
                }
                if let notes = s.dns_diagnosis?.notes, !notes.isEmpty {
                    Panel(title: "Diagnosis") { ForEach(notes, id: \.self) { Text($0) } }
                }
                ForEach(resolvers) { r in
                    Panel(title: "Resolver \(r.index)") {
                        LabeledContent("Interface", value: r.interface ?? "default")
                        LabeledContent("Domain", value: r.domain ?? "default")
                        LabeledContent("Servers", value: (r.nameservers ?? []).joined(separator: ", ").isEmpty ? "—" : (r.nameservers ?? []).joined(separator: ", "))
                    }
                }
                if resolvers.isEmpty { Panel { Text("No DNS resolver reported.").foregroundStyle(Palette.textSecondary) } }
            }
        }
    }
}

struct RoutesView: View {
    @EnvironmentObject var store: NivoraStore
    var body: some View {
        let routes = store.snapshot?.routes ?? []
        Table(routes) {
            TableColumn("Family") { Text($0.family) }
            TableColumn("Destination") { Text($0.default ? "default" : $0.destination).font(.system(.callout, design: .monospaced)) }
            TableColumn("Gateway") { Text($0.gateway.isEmpty ? "—" : $0.gateway).font(.system(.callout, design: .monospaced)) }
            TableColumn("Interface") { StatusPill(text: $0.interface, kind: "neutral") }
            TableColumn("Flags") { Text($0.flags).font(.system(.caption, design: .monospaced)).foregroundStyle(Palette.textSecondary) }
        }
        .overlay { if routes.isEmpty { ContentUnavailableView("No routes", systemImage: "arrow.triangle.branch", description: Text("The collector reported no routing table.")) } }
    }
}

struct VPNView: View {
    @EnvironmentObject var store: NivoraStore
    var body: some View {
        if let s = store.snapshot {
            Page {
                Panel(title: "Network connections", subtitle: "VPN and tunnel services known to macOS") {
                    ForEach(s.vpn) { v in
                        LabeledContent(v.name) { StatusPill(text: v.active ? "Active" : v.status, kind: v.active ? "active" : "neutral") }
                    }
                    if s.vpn.isEmpty { Text("No VPN or tunnel services configured.").foregroundStyle(Palette.textSecondary) }
                }
                if s.vpn.contains(where: \.active), s.dns_diagnosis?.public == true {
                    Panel(title: "Check DNS") { Text("A VPN is active while public resolvers are in use. Confirm DNS is routed through the tunnel on the DNS pane.") }
                }
            }
        }
    }
}

/// ⌘K: jump to a pane or app, or run a common action.
struct CommandPaletteView: View {
    @EnvironmentObject var store: NivoraStore
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""
    @State private var selection: PaletteItem.ID?
    @FocusState private var focused: Bool

    private var items: [PaletteItem] {
        var out = Pane.allCases.map { PaletteItem(id: "pane:\($0.rawValue)", title: $0.rawValue, detail: $0.subtitle, symbol: $0.symbol, kind: .pane($0)) }
        out += [
            PaletteItem(id: "act:pause", title: store.paused ? "Resume sampling" : "Pause sampling", detail: "Action", symbol: store.paused ? "play.fill" : "pause.fill", kind: .action(.pause)),
            PaletteItem(id: "act:refresh", title: "Refresh now", detail: "Action", symbol: "arrow.clockwise", kind: .action(.refresh)),
            PaletteItem(id: "act:thisMac", title: "Monitor this Mac", detail: "Source", symbol: "laptopcomputer", kind: .action(.thisMac)),
            PaletteItem(id: "act:demo", title: "Show demo data", detail: "Source", symbol: "play.rectangle", kind: .action(.demo)),
            PaletteItem(id: "act:shortcuts", title: "Keyboard shortcuts", detail: "Help", symbol: "keyboard", kind: .action(.shortcuts)),
        ]
        out += (store.snapshot?.apps ?? []).map { PaletteItem(id: "app:\($0.name)", title: $0.name, detail: "Application · \($0.connections) connections", symbol: "app", kind: .app($0.name)) }
        return out
    }
    private var results: [PaletteItem] { PaletteSearch.rank(query, items) }

    var body: some View {
        VStack(spacing: 0) {
            TextField("Go to a pane, app or action", text: $query)
                .textFieldStyle(.plain).font(.title3).padding(16).focused($focused)
                .onSubmit { run(results.first { $0.id == selection } ?? results.first) }
                .onChange(of: query) { _, _ in selection = results.first?.id }
                .accessibilityLabel("Command palette search")
            Divider()
            List(results, selection: $selection) { item in
                Label { VStack(alignment: .leading) { Text(item.title); Text(item.detail).font(.caption).foregroundStyle(Palette.textSecondary).lineLimit(1) } }
                    icon: { Image(systemName: item.symbol) }
                    .tag(item.id)
                    .contentShape(Rectangle())
                    .onTapGesture { run(item) }
                    .accessibilityElement(children: .combine)
            }
            .listStyle(.plain)
        }
        .frame(width: 560, height: 420)
        .onAppear { focused = true; selection = results.first?.id }
        .onExitCommand { dismiss() }
    }

    private func run(_ item: PaletteItem?) {
        guard let item else { return }
        dismiss()
        switch item.kind {
        case .pane(let p): store.pane = p
        case .app(let name): store.selectedApp = name
        case .action(let a):
            switch a {
            case .pause: store.paused.toggle()
            case .refresh: Task { await store.refresh() }
            case .demo: store.useDemo()
            case .thisMac: store.useThisMac()
            case .shortcuts: NotificationCenter.default.post(name: .nivoraShowShortcuts, object: nil)
            }
        }
    }
}
