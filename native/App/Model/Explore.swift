// SPDX-License-Identifier: BUSL-1.1
import Foundation

/// Pure helpers behind the Domains, Network Map and command-palette views, kept free of SwiftUI so they are unit-testable.
enum Explore {
    /// Mirrors the collector's `endpoint_host`: `[v6]:port`, `host:port`; a bare IPv6 address is returned whole.
    static func host(_ endpoint: String) -> String {
        let e = endpoint.trimmingCharacters(in: .whitespaces)
        if e.hasPrefix("["), let close = e.firstIndex(of: "]") { return String(e[e.index(after: e.startIndex)..<close]) }
        if e.filter({ $0 == ":" }).count == 1, let i = e.lastIndex(of: ":") { return String(e[..<i]) }
        return e
    }

    static func port(_ endpoint: String) -> Int? {
        let e = endpoint.trimmingCharacters(in: .whitespaces)
        if e.hasPrefix("["), e.contains("]:"), let i = e.lastIndex(of: ":") { return Int(e[e.index(after: i)...]) }
        if e.filter({ $0 == ":" }).count == 1, let i = e.lastIndex(of: ":") { return Int(e[e.index(after: i)...]) }
        return nil
    }
}

struct DomainSummary: Identifiable, Equatable {
    var id: String { host }
    let host: String
    var flows = 0
    var bytes = 0
    var apps: [String] = []
    var ports: [Int] = []

    /// Groups flows by remote host, busiest (most bytes) first.
    static func make(from flows: [NivoraSnapshot.Flow]) -> [DomainSummary] {
        var by: [String: DomainSummary] = [:]
        for f in flows {
            let h = Explore.host(f.remote)
            guard !h.isEmpty else { continue }
            var d = by[h] ?? DomainSummary(host: h)
            d.flows += 1
            d.bytes += f.bytes_in + f.bytes_out
            if !d.apps.contains(f.process) { d.apps.append(f.process) }
            if let p = Explore.port(f.remote), !d.ports.contains(p) { d.ports.append(p) }
            by[h] = d
        }
        return by.values.map { var d = $0; d.ports.sort(); return d }
            .sorted { ($0.bytes, $1.host) > ($1.bytes, $0.host) }
    }
}

/// Three columns for the Network Map: applications, interfaces, destinations, with the links between visible nodes.
struct MapLayout {
    let apps: [NivoraSnapshot.Topology.Node]
    let interfaces: [NivoraSnapshot.Topology.Node]
    let destinations: [NivoraSnapshot.Topology.Node]
    let links: [NivoraSnapshot.Topology.Edge]

    var rows: Int { max(apps.count, interfaces.count, destinations.count) }
    var maxBps: Double { max(links.map(\.bps).max() ?? 0, 1) }

    /// (column 0...2, row) of a node, or nil if it is not shown.
    func position(of id: String) -> (column: Int, row: Int)? {
        if let r = apps.firstIndex(where: { $0.id == id }) { return (0, r) }
        if let r = interfaces.firstIndex(where: { $0.id == id }) { return (1, r) }
        if let r = destinations.firstIndex(where: { $0.id == id }) { return (2, r) }
        return nil
    }

    static func make(_ t: NivoraSnapshot.Topology, maxApps: Int = 12, maxDestinations: Int = 16) -> MapLayout {
        var weight: [String: Double] = [:]
        for e in t.edges { weight[e.source, default: 0] += e.bps; weight[e.target, default: 0] += e.bps }
        func ranked(_ kinds: (String) -> Bool, _ limit: Int) -> [NivoraSnapshot.Topology.Node] {
            Array(t.nodes.filter { kinds($0.kind) }
                .sorted { (weight[$0.id] ?? 0, $1.label) > (weight[$1.id] ?? 0, $0.label) }.prefix(limit))
        }
        let apps = ranked({ $0 == "app" }, maxApps)
        let ifaces = ranked({ $0 == "interface" }, 8)
        let dests = ranked({ $0 != "app" && $0 != "interface" && $0 != "host" }, maxDestinations)
        let visible = Set((apps + ifaces + dests).map(\.id))
        return MapLayout(apps: apps, interfaces: ifaces, destinations: dests,
                         links: t.edges.filter { visible.contains($0.source) && visible.contains($0.target) })
    }
}

/// One entry in the ⌘K palette.
struct PaletteItem: Identifiable, Equatable {
    enum Kind: Equatable { case pane(Pane), app(String), action(Action) }
    enum Action: String, Equatable { case pause, refresh, demo, thisMac, shortcuts }
    let id: String
    let title: String
    let detail: String
    let symbol: String
    let kind: Kind
}

enum PaletteSearch {
    /// 0 = no match. Prefix beats word-prefix beats substring beats in-order letters.
    static func score(_ query: String, _ text: String) -> Int {
        let q = query.lowercased().trimmingCharacters(in: .whitespaces)
        let t = text.lowercased()
        if q.isEmpty { return 1 }
        if t.hasPrefix(q) { return 100 - min(t.count, 50) / 2 }
        if t.split(whereSeparator: { !$0.isLetter && !$0.isNumber }).contains(where: { $0.hasPrefix(q) }) { return 70 }
        if t.contains(q) { return 50 }
        var it = t.makeIterator()
        for ch in q { var found = false; while let c = it.next() { if c == ch { found = true; break } }; if !found { return 0 } }
        return 20
    }

    static func rank(_ query: String, _ items: [PaletteItem], limit: Int = 30) -> [PaletteItem] {
        let scored = items.enumerated().compactMap { i, item -> (Int, Int, PaletteItem)? in
            let s = max(score(query, item.title), score(query, item.detail) / 2)
            return s > 0 ? (s, i, item) : nil
        }
        return scored.sorted { ($0.0, -$0.1) > ($1.0, -$1.1) }.prefix(limit).map(\.2)
    }
}
