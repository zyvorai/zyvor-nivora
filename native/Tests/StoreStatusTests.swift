// SPDX-License-Identifier: BUSL-1.1
import XCTest

final class StoreStatusTests: XCTestCase {
    func testFailedPollDuringStartupIsStartingNotAnError() {
        XCTAssertEqual(CollectorStartup.outcome(hasSnapshot: false, sinceStart: 0.1, message: "refused"), .starting)
        XCTAssertEqual(CollectorStartup.outcome(hasSnapshot: false, sinceStart: 19.9, message: "refused"), .starting)
    }

    func testFailedPollAfterTheGracePeriodWithNoDataIsReported() {
        XCTAssertEqual(CollectorStartup.outcome(hasSnapshot: false, sinceStart: 20, message: "refused"), .failed("refused"))
        XCTAssertEqual(CollectorStartup.outcome(hasSnapshot: false, sinceStart: 300, message: "refused"), .failed("refused"))
    }

    func testFailedPollNeverReplacesDataAlreadyShown() {
        XCTAssertEqual(CollectorStartup.outcome(hasSnapshot: true, sinceStart: 0.1, message: "refused"), .keep)
        XCTAssertEqual(CollectorStartup.outcome(hasSnapshot: true, sinceStart: 500, message: "refused"), .keep)
    }
}
