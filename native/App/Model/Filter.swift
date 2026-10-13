// SPDX-License-Identifier: BUSL-1.1
import Foundation

/// Flow filter grammar shared with the collector (`parse_filter`) and the web UI (`parseFilter`).
/// Parity is enforced by tests/fixtures/filter-vectors.json.
struct FilterTerm: Hashable {
    enum Kind: String { case app, host, port, proto, iface, state, source, rate, text }
    let kind: Kind
    var value = ""
    var negate = false
    var above = true          // rate: true for '>', false for '<'
    var bits = 0.0            // rate threshold in bits/s
}

/// The fields a filter inspects; both `Flow` and a projected `AppItem` map onto it.
struct FilterSubject {
    var process = "", bundleID = "", local = "", remote = "", proto = "", state = "", interface = "", source = ""
    var totalBps = 0.0
    var haystack = ""         // lower-cased text searched by free-text terms
}

enum FlowFilter {
    private static let keys: [String: FilterTerm.Kind] = [
        "app": .app, "process": .app, "host": .host, "port": .port, "proto": .proto, "protocol": .proto,
        "iface": .iface, "interface": .iface, "state": .state, "source": .source,
    ]
    private static let units: [String: Double] = ["bps": 1, "kbps": 1e3, "mbps": 1e6, "gbps": 1e9]

    static func tokens(_ query: String) -> [String] {
        var out: [String] = [], cur = "", quoted = false
        for ch in query {
            if ch == "\"" { quoted.toggle() }
            else if ch.isWhitespace && !quoted { if !cur.isEmpty { out.append(cur) }; cur = "" }
            else { cur.append(ch) }
        }
        if !cur.isEmpty { out.append(cur) }
        return out
    }

    static func parse(_ query: String) -> [FilterTerm] {
        tokens(query).map { tok in
            let lower = tok.lowercased()
            if let first = lower.first, first == ">" || first == "<" {
                // longest unit suffix first so "kbps" is not read as "bps"
                for unit in ["gbps", "mbps", "kbps", "bps"] where lower.hasSuffix(unit) {
                    if let n = Double(lower.dropFirst().dropLast(unit.count)) {
                        return FilterTerm(kind: .rate, above: first == ">", bits: n * (units[unit] ?? 1))
                    }
                }
            }
            let negate = (tok.first == "!" || tok.first == "-") && tok.count > 1
            let body = negate ? String(tok.dropFirst()) : tok
            if let i = body.firstIndex(of: ":"), i != body.startIndex {
                let key = body[..<i].lowercased(), value = String(body[body.index(after: i)...])
                if let kind = keys[key], !value.isEmpty { return FilterTerm(kind: kind, value: value.lowercased(), negate: negate) }
            }
            let bang = tok.first == "!" && tok.count > 1
            return FilterTerm(kind: .text, value: (bang ? String(tok.dropFirst()) : tok).lowercased(), negate: bang)
        }
    }

    static func host(of endpoint: String) -> String {
        let e = endpoint.trimmingCharacters(in: .whitespaces)
        if e.hasPrefix("["), let close = e.firstIndex(of: "]") { return String(e[e.index(after: e.startIndex)..<close]) }
        return e.filter({ $0 == ":" }).count == 1 ? String(e.split(separator: ":", omittingEmptySubsequences: false)[0]) : e
    }

    static func port(of endpoint: String) -> Int {
        let e = endpoint.trimmingCharacters(in: .whitespaces)
        if e.hasPrefix("["), let r = e.range(of: "]:") { return Int(e[r.upperBound...]) ?? 0 }
        if e.filter({ $0 == ":" }).count == 1 { return Int(e.split(separator: ":", omittingEmptySubsequences: false)[1]) ?? 0 }
        return 0
    }

    private static func hit(_ s: FilterSubject, _ t: FilterTerm) -> Bool {
        let v = t.value
        switch t.kind {
        case .app: return s.process.lowercased().contains(v) || s.bundleID.lowercased().contains(v)
        case .host: return host(of: s.remote).lowercased().contains(v)
        case .port:
            let parts = v.split(separator: "-", maxSplits: 1).map(String.init)
            guard let a = Int(parts[0]), let b = Int(parts.count > 1 ? parts[1] : parts[0]) else { return false }
            return [port(of: s.remote), port(of: s.local)].contains { $0 != 0 && $0 >= a && $0 <= b }
        case .proto: return s.proto.lowercased() == v
        case .iface: return s.interface.lowercased() == v
        case .state: return s.state.lowercased() == v
        case .source: return s.source.lowercased() == v
        case .rate: return true
        case .text: return s.haystack.contains(v)
        }
    }

    static func matches(_ s: FilterSubject, _ terms: [FilterTerm]) -> Bool {
        var groups: [FilterTerm.Kind: [FilterTerm]] = [:]
        for t in terms {
            if t.kind == .rate {
                let bits = s.totalBps * 8
                if t.above ? !(bits > t.bits) : !(bits < t.bits) { return false }
            } else if t.negate {
                if hit(s, t) { return false }
            } else { groups[t.kind, default: []].append(t) }
        }
        return groups.values.allSatisfy { $0.contains { hit(s, $0) } }
    }
}

extension NivoraSnapshot.Flow {
    var filterSubject: FilterSubject {
        FilterSubject(process: process, bundleID: bundle_id ?? "", local: local, remote: remote, proto: `protocol`,
                      state: state, interface: interface, source: source, totalBps: total_bps,
                      haystack: [process, bundle_id ?? "", `protocol`, local, remote, state, interface, source].joined(separator: " ").lowercased())
    }
}

extension NivoraSnapshot.AppItem {
    var filterSubject: FilterSubject {
        FilterSubject(process: name, bundleID: bundle_id ?? "", remote: domains.first ?? "", interface: interfaces.first ?? "",
                      totalBps: total_bps, haystack: ([name, bundle_id ?? ""] + domains + interfaces).joined(separator: " ").lowercased())
    }
}

struct SavedView: Codable, Identifiable, Hashable {
    var id: String { query }
    let name: String
    let query: String

    /// Mirrors mergePrefs() in web/lib.js: trims names, drops blanks/duplicates, caps the list at 20.
    static func sanitized(_ views: [SavedView]) -> [SavedView] {
        var seen = Set<String>(), out: [SavedView] = []
        for v in views {
            let name = String(v.name.trimmingCharacters(in: .whitespaces).prefix(40))
            let query = String(v.query.prefix(200))
            guard !name.isEmpty, !query.isEmpty, seen.insert(query).inserted else { continue }
            out.append(SavedView(name: name, query: query))
        }
        return Array(out.prefix(20))
    }
}

/// Summary rows for the grouped Flows views; mirrors `groupFlows` in web/lib.js.
struct FlowGroup: Identifiable, Hashable {
    enum By: String, CaseIterable, Identifiable { case flat = "Flat", app = "By app", host = "By host", interface = "By interface"
        var id: Self { self } }
    var id: String { key }
    let key: String
    var count = 0
    var rx = 0.0, tx = 0.0
    var bytesIn = 0, bytesOut = 0

    static func group(_ flows: [NivoraSnapshot.Flow], by: By) -> [FlowGroup] {
        guard by != .flat else { return [] }
        var map: [String: FlowGroup] = [:]
        for f in flows {
            let key: String
            switch by {
            case .app: key = f.process.isEmpty ? "Unknown" : f.process
            case .host: key = FlowFilter.host(of: f.remote)
            case .interface: key = f.interface.isEmpty ? "—" : f.interface
            case .flat: continue
            }
            var g = map[key] ?? FlowGroup(key: key)
            g.count += 1; g.rx += f.rx_bps; g.tx += f.tx_bps; g.bytesIn += f.bytes_in; g.bytesOut += f.bytes_out
            map[key] = g
        }
        return map.values.sorted { ($0.rx + $0.tx, $1.key) > ($1.rx + $1.tx, $0.key) }
    }
}

/// What changed between a pinned baseline and the current sample; mirrors `diffFlows` in web/lib.js.
struct FlowDiff {
    let added: [NivoraSnapshot.Flow]
    let removed: [NivoraSnapshot.Flow]
    let changed: [(flow: NivoraSnapshot.Flow, delta: Double)]

    static func compare(before: [NivoraSnapshot.Flow], after: [NivoraSnapshot.Flow], topN: Int = 8) -> FlowDiff {
        let a = Dictionary(before.map { ($0.id, $0) }, uniquingKeysWith: { _, last in last })
        let b = Dictionary(after.map { ($0.id, $0) }, uniquingKeysWith: { _, last in last })
        let added = after.filter { a[$0.id] == nil }
        let removed = before.filter { b[$0.id] == nil }
        let moved = after.compactMap { f -> (NivoraSnapshot.Flow, Double)? in
            guard let old = a[f.id], f.total_bps != old.total_bps else { return nil }
            return (f, f.total_bps - old.total_bps)
        }.sorted { abs($0.1) > abs($1.1) }
        return FlowDiff(added: added, removed: removed, changed: Array(moved.prefix(topN)).map { (flow: $0.0, delta: $0.1) })
    }
}

extension FlowFilter {
    /// Chips for the filter bar: the same tokenisation the matcher uses.
    static func chips(_ query: String) -> [String] { tokens(query) }

    /// Re-quotes values containing spaces so `app:"Google Chrome"` survives a chip removal.
    static func dropChip(_ query: String, at index: Int) -> String {
        tokens(query).enumerated().filter { $0.offset != index }.map { _, t in
            guard t.contains(where: \.isWhitespace) else { return t }
            if let i = t.firstIndex(of: ":") { return "\(t[...i])\"\(t[t.index(after: i)...])\"" }
            return "\"\(t)\""
        }.joined(separator: " ")
    }
}

/// Time Machine grouping and filtering, pure so it can be unit tested.
enum TimelineKit {
    struct Day: Identifiable { let id: String; let events: [NivoraSnapshot.Event] }

    static func kinds(_ events: [NivoraSnapshot.Event]) -> [String] {
        Array(Set(events.map(\.kind))).sorted()
    }

    /// Newest first; `kind == nil` keeps all kinds; `query` matches title and detail case-insensitively.
    static func filter(_ events: [NivoraSnapshot.Event], kind: String?, query: String) -> [NivoraSnapshot.Event] {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        return events.filter { e in
            (kind == nil || e.kind == kind) &&
            (q.isEmpty || e.title.lowercased().contains(q) || (e.detail ?? "").lowercased().contains(q) || e.kind.lowercased().contains(q))
        }
        .sorted { $0.ts > $1.ts }
    }

    /// Groups already-sorted events by calendar day of their ISO-8601 timestamp (first 10 chars).
    static func byDay(_ events: [NivoraSnapshot.Event]) -> [Day] {
        var order: [String] = [], map: [String: [NivoraSnapshot.Event]] = [:]
        for e in events {
            let day = String(e.ts.prefix(10))
            if map[day] == nil { order.append(day) }
            map[day, default: []].append(e)
        }
        return order.map { Day(id: $0, events: map[$0]!) }
    }

    static func symbol(for kind: String) -> String {
        switch kind {
        case "interface": return "network"
        case "dns": return "magnifyingglass"
        case "route": return "arrow.triangle.turn.up.right.diamond"
        case "vpn": return "lock.shield"
        case "listener": return "antenna.radiowaves.left.and.right"
        case "traffic": return "chart.line.uptrend.xyaxis"
        case "behavior": return "eye"
        case "capture": return "record.circle"
        case "startup": return "power"
        default: return "clock"
        }
    }
}
