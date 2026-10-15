// SPDX-License-Identifier: BUSL-1.1
import XCTest

final class WidgetDataTests: XCTestCase {
    private func sample(updated: Date) -> WidgetData {
        WidgetData(updated: updated, host: "mac", simulated: false, health: 90, download: 10, upload: 5, flows: 3, findings: 0,
                   topApps: [.init(name: "Safari", bps: 9)])
    }

    func testStalenessAndAge() {
        let now = Date()
        XCTAssertFalse(sample(updated: now.addingTimeInterval(-30)).isStale(now: now))
        XCTAssertTrue(sample(updated: now.addingTimeInterval(-300)).isStale(now: now))
        XCTAssertEqual(sample(updated: now.addingTimeInterval(-30)).age(now: now), "30 s ago")
        XCTAssertEqual(sample(updated: now.addingTimeInterval(-300)).age(now: now), "5 min ago")
    }

    func testRoundTripThroughContainerDirectory() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("nivora-widget-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: dir) }
        let data = sample(updated: Date(timeIntervalSince1970: 1_700_000_000))
        XCTAssertTrue(WidgetStore.write(data, in: dir))
        XCTAssertEqual(WidgetStore.read(in: dir), data)
    }

    func testNothingIsWrittenWithoutAWidgetContainer() {
        let home = FileManager.default.temporaryDirectory.appendingPathComponent("no-home-\(UUID().uuidString)")
        XCTAssertNil(WidgetStore.directory(home: home, sandboxed: false))
        XCTAssertFalse(WidgetStore.write(sample(updated: Date()), in: nil))
        XCTAssertNil(WidgetStore.read(in: nil))
    }

    func testContainerDirectoryIsUsedOnceItExists() throws {
        let home = FileManager.default.temporaryDirectory.appendingPathComponent("home-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: home) }
        let container = home.appendingPathComponent("Library/Containers/\(WidgetStore.widgetBundleID)/Data")
        try FileManager.default.createDirectory(at: container, withIntermediateDirectories: true)
        XCTAssertNotNil(WidgetStore.directory(home: home, sandboxed: false))
    }
}
