// SPDX-License-Identifier: BUSL-1.1
import Foundation
import WidgetKit

/// Publishes the latest sample for the widget. Throttled: a fresh file every few seconds, and a WidgetKit
/// reload at most about every half minute. A no-op until the widget's container exists.
@MainActor
final class WidgetBridge {
    private var lastWrite = Date.distantPast
    private var lastReload = Date.distantPast

    func publish(_ s: NivoraSnapshot, now: Date = Date()) {
        guard now.timeIntervalSince(lastWrite) >= 5 else { return }
        lastWrite = now
        let top = s.apps.sorted { $0.total_bps > $1.total_bps }.prefix(5).map { WidgetData.App(name: $0.name, bps: $0.total_bps) }
        let data = WidgetData(updated: now, host: s.host.name, simulated: s.host.demo, health: s.health.score,
                              download: s.traffic.rx_bps, upload: s.traffic.tx_bps, flows: s.flows.count,
                              findings: s.findings.count, topApps: Array(top))
        guard WidgetStore.write(data) else { return }
        if now.timeIntervalSince(lastReload) >= 30 {
            lastReload = now
            WidgetCenter.shared.reloadAllTimelines()
        }
    }
}
