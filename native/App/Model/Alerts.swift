// SPDX-License-Identifier: BUSL-1.1
import Foundation

/// Observe-first alerts: they describe what was seen and link to evidence; they never enforce.
struct NivoraAlert: Identifiable, Hashable {
    enum Severity: Int, Comparable { case info = 0, warning, critical
        static func < (a: Self, b: Self) -> Bool { a.rawValue < b.rawValue } }
    let id: String
    let severity: Severity
    let title: String
    let detail: String
    let app: String?
}

enum AlertRules {
    static let defaultThresholdMbps = 0.0   // 0 = rate alerts off

    static func compute(_ s: NivoraSnapshot, thresholdMbps: Double) -> [NivoraAlert] {
        var out: [NivoraAlert] = s.findings.map {
            NivoraAlert(id: "finding-\($0.id)",
                        severity: $0.severity == "critical" ? .critical : $0.severity == "info" ? .info : .warning,
                        title: $0.title, detail: $0.detail, app: nil)
        }
        if thresholdMbps > 0 {
            let limit = thresholdMbps * 1_000_000 / 8
            for a in s.apps where a.total_bps > limit {
                out.append(NivoraAlert(id: "rate-\(a.name)", severity: .warning, title: "\(a.name) is above \(Int(thresholdMbps)) Mbit/s",
                                       detail: "\(rateString(a.total_bps)) across \(a.connections) connections. Observing only.", app: a.name))
            }
        }
        if s.health.score < 50 {
            out.append(NivoraAlert(id: "health-poor", severity: .critical, title: "Network health is poor (\(s.health.score)/100)",
                                   detail: s.health.components.filter { $0.score < 60 }.map(\.detail).joined(separator: " · "), app: nil))
        }
        return out
    }
}
