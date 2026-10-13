// SPDX-License-Identifier: BUSL-1.1
import XCTest
import Foundation

final class SnapshotTests: XCTestCase {
    private func fixture() throws -> Data {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .appendingPathComponent("Fixtures/demo-snapshot.json")
        return try Data(contentsOf: url)
    }

    func testDemoSnapshotDecodes() throws {
        let s = try JSONDecoder().decode(NivoraSnapshot.self, from: fixture())
        XCTAssertTrue(s.host.demo)
        XCTAssertFalse(s.apps.isEmpty)
        XCTAssertFalse(s.flows.isEmpty)
        XCTAssertTrue((0...100).contains(s.health.score))
    }

    func testOptionalSectionsMayBeMissing() throws {
        var obj = try JSONSerialization.jsonObject(with: fixture()) as! [String: Any]
        for k in ["wifi", "routes", "behavior", "fluxvm", "rules"] { obj.removeValue(forKey: k) }
        let data = try JSONSerialization.data(withJSONObject: obj)
        let s = try JSONDecoder().decode(NivoraSnapshot.self, from: data)
        XCTAssertNil(s.fluxvm)
        XCTAssertNil(s.rules)
    }

    func testFormatters() {
        XCTAssertFalse(byteString(0).isEmpty)
        XCTAssertTrue(byteString(1_048_576).contains("MB"))
        XCTAssertTrue(rateString(2048).hasSuffix("/s"))
    }
}

final class AlertTests: XCTestCase {
    private func snapshot(score: Int? = nil) throws -> NivoraSnapshot {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .appendingPathComponent("Fixtures/demo-snapshot.json")
        var obj = try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as! [String: Any]
        if let score, var h = obj["health"] as? [String: Any] { h["score"] = score; obj["health"] = h }
        return try JSONDecoder().decode(NivoraSnapshot.self, from: JSONSerialization.data(withJSONObject: obj))
    }

    func testRateAlertsOffByDefault() throws {
        let alerts = AlertRules.compute(try snapshot(score: 90), thresholdMbps: 0)
        XCTAssertFalse(alerts.contains { $0.id.hasPrefix("rate-") })
    }

    func testRateAlertFiresAboveThreshold() throws {
        let s = try snapshot(score: 90)
        let alerts = AlertRules.compute(s, thresholdMbps: 0.000001)
        XCTAssertTrue(alerts.contains { $0.id.hasPrefix("rate-") })
    }

    func testPoorHealthIsCritical() throws {
        let alerts = AlertRules.compute(try snapshot(score: 20), thresholdMbps: 0)
        XCTAssertEqual(alerts.first { $0.id == "health-poor" }?.severity, .critical)
    }
}

final class ExportTests: XCTestCase {
    func testCellNeutralisesFormulasAndQuotes() {
        XCTAssertEqual(FlowExport.cell("=1+1"), "'=1+1")
        XCTAssertEqual(FlowExport.cell("a,b"), "\"a,b\"")
        XCTAssertEqual(FlowExport.cell("say \"hi\""), "\"say \"\"hi\"\"\"")
        XCTAssertEqual(FlowExport.cell("Safari"), "Safari")
    }

    func testCSVHasHeaderAndOneRowPerFlow() throws {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("Fixtures/demo-snapshot.json")
        let s = try JSONDecoder().decode(NivoraSnapshot.self, from: Data(contentsOf: url))
        let lines = FlowExport.csv(s.flows).split(separator: "\n")
        XCTAssertEqual(lines.count, s.flows.count + 1)
        XCTAssertTrue(lines[0].hasPrefix("process,protocol"))
    }
}

final class FilterTests: XCTestCase {
    private struct Vectors: Decodable {
        struct Case: Decodable { let q: String; let expect: [String] }
        let flows: [NivoraSnapshot.Flow]
        let cases: [Case]
    }

    func testSharedVectorsMatchCollectorAndWeb() throws {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("../../tests/fixtures/filter-vectors.json")
        let v = try JSONDecoder().decode(Vectors.self, from: Data(contentsOf: url))
        for c in v.cases {
            let terms = FlowFilter.parse(c.q)
            let got = v.flows.filter { terms.isEmpty || FlowFilter.matches($0.filterSubject, terms) }.map(\.id)
            XCTAssertEqual(got, c.expect, "query: \(c.q)")
        }
    }
}

final class SavedViewTests: XCTestCase {
    func testSanitizeTrimsDedupesAndCaps() {
        let raw = [SavedView(name: " A ", query: "port:443"), SavedView(name: "", query: "x"),
                   SavedView(name: "dup", query: "port:443")] + (0..<30).map { SavedView(name: "v\($0)", query: "q\($0)") }
        let out = SavedView.sanitized(raw)
        XCTAssertEqual(out.first?.name, "A")
        XCTAssertEqual(out.count, 20)
        XCTAssertEqual(Set(out.map(\.query)).count, out.count)
    }
}

final class GroupTests: XCTestCase {
    func testGroupsMatchWebSemantics() throws {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("../../tests/fixtures/filter-vectors.json")
        struct V: Decodable { let flows: [NivoraSnapshot.Flow] }
        let flows = try JSONDecoder().decode(V.self, from: Data(contentsOf: url)).flows
        XCTAssertTrue(FlowGroup.group(flows, by: .flat).isEmpty)
        let byApp = FlowGroup.group(flows, by: .app)
        XCTAssertEqual(byApp.first?.key, "Safari")                 // highest live rate
        XCTAssertEqual(byApp.map(\.count).reduce(0, +), flows.count)
        XCTAssertTrue(FlowGroup.group(flows, by: .host).contains { $0.key == "2001:db8::7" })
    }
}

final class DiffAndChipTests: XCTestCase {
    func testDropChipKeepsQuotedValues() {
        XCTAssertEqual(FlowFilter.dropChip("app:\"Google Chrome\" port:443", at: 1), "app:\"Google Chrome\"")
        XCTAssertEqual(FlowFilter.dropChip("app:\"Google Chrome\" port:443", at: 0), "port:443")
    }

    func testDiffMatchesWebSemantics() throws {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("../../tests/fixtures/filter-vectors.json")
        struct V: Decodable { let flows: [NivoraSnapshot.Flow] }
        let flows = try JSONDecoder().decode(V.self, from: Data(contentsOf: url)).flows   // a, b, c, d
        let d = FlowDiff.compare(before: Array(flows[0...1]), after: [flows[0], flows[2]])
        XCTAssertEqual(d.added.map(\.id), ["c"])
        XCTAssertEqual(d.removed.map(\.id), ["b"])
        XCTAssertTrue(d.changed.isEmpty)
    }
}
