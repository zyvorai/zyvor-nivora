// SPDX-License-Identifier: BUSL-1.1
import Foundation
import NetworkExtension

final class FilterControlProvider: NEFilterControlProvider {
    override func startFilter(completionHandler: @escaping (Error?) -> Void) {
        completionHandler(nil)
    }

    override func stopFilter(with reason: NEProviderStopReason, completionHandler: @escaping () -> Void) {
        completionHandler()
    }

    override func handle(_ report: NEFilterReport) {
        guard let flow = report.flow else { return }
        let event: String
        switch report.event {
        case .newFlow: event = "new"
        case .dataDecision: event = "data"
        case .flowClosed: event = "closed"
        case .statistics: event = "statistics"
        @unknown default: event = "report"
        }
        EventWriter.shared.append(
            FlowIdentity.make(
                flow: flow,
                event: event,
                bytesIn: report.bytesInboundCount,
                bytesOut: report.bytesOutboundCount
            )
        )
    }
}
