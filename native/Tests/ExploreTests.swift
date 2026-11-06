// SPDX-License-Identifier: BUSL-1.1
import XCTest
import Foundation

final class ExploreTests: XCTestCase {
    private func snapshot() throws -> NivoraSnapshot {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("Fixtures/demo-snapshot.json")
        return try JSONDecoder().decode(NivoraSnapshot.self, from: Data(contentsOf: url))
    }

    func testEndpointParsing() {
        XCTAssertEqual(Explore.host("1.2.3.4:443"), "1.2.3.4")
        XCTAssertEqual(Explore.port("1.2.3.4:443"), 443)
        XCTAssertEqual(Explore.host("[2606:4700::1]:443"), "2606:4700::1")
        XCTAssertEqual(Explore.port("[2606:4700::1]:443"), 443)
        XCTAssertEqual(Explore.host("fe80::1"), "fe80::1")
        XCTAssertNil(Explore.port("fe80::1"))
        XCTAssertEqual(Explore.host(""), "")
    }

    func testDomainsGroupFlowsByHost() throws {
        let s = try snapshot()
        let domains = DomainSummary.make(from: s.flows)
        XCTAssertFalse(domains.isEmpty)
        XCTAssertEqual(domains.map(\.flows).reduce(0, +), s.flows.filter { !Explore.host($0.remote).isEmpty }.count)
        XCTAssertEqual(domains.map(\.bytes), domains.map(\.bytes).sorted(by: >))
        XCTAssertEqual(Set(domains.map(\.host)).count, domains.count)
    }

    func testDemoSnapshotHasTopologyAndResolvers() throws {
        let s = try snapshot()
        XCTAssertNotNil(s.topology)
        XCTAssertFalse(s.dns.resolvers?.isEmpty ?? true)
    }

    func testMapLayoutColumnsAndLinks() throws {
        let t = try XCTUnwrap(snapshot().topology)
        let layout = MapLayout.make(t, maxApps: 3, maxDestinations: 4)
        XCTAssertLessThanOrEqual(layout.apps.count, 3)
        XCTAssertLessThanOrEqual(layout.destinations.count, 4)
        XCTAssertTrue(layout.apps.allSatisfy { $0.kind == "app" })
        XCTAssertTrue(layout.interfaces.allSatisfy { $0.kind == "interface" })
        XCTAssertFalse((layout.apps + layout.interfaces + layout.destinations).contains { $0.kind == "host" })
        for e in layout.links {
            XCTAssertNotNil(layout.position(of: e.source))
            XCTAssertNotNil(layout.position(of: e.target))
        }
        XCTAssertGreaterThan(layout.maxBps, 0)
    }

    func testPaletteRanking() {
        func item(_ t: String) -> PaletteItem { PaletteItem(id: t, title: t, detail: "", symbol: "x", kind: .action(.refresh)) }
        let items = ["Time Machine", "Timeline thing", "DNS", "Domains", "Network Map"].map(item)
        XCTAssertEqual(PaletteSearch.rank("dns", items).first?.title, "DNS")
        XCTAssertEqual(PaletteSearch.rank("map", items).first?.title, "Network Map")
        XCTAssertEqual(PaletteSearch.rank("tm", items).first?.title, "Time Machine")   // in-order letters
        XCTAssertTrue(PaletteSearch.rank("zzz", items).isEmpty)
        XCTAssertEqual(PaletteSearch.rank("", items).count, items.count)
    }

    func testEveryPaneHasSectionSymbolAndSubtitle() {
        for p in Pane.allCases {
            XCTAssertFalse(p.symbol.isEmpty)
            XCTAssertFalse(p.subtitle.isEmpty)
        }
        XCTAssertEqual(Set(Pane.allCases.map(\.rawValue)).count, Pane.allCases.count)
    }
}
