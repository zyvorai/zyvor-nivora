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
