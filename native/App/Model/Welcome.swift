// SPDX-License-Identifier: BUSL-1.1
import Foundation

/// First-run gating, kept pure so it can be unit tested.
enum WelcomeGate {
    static let defaultsKey = "nivora.welcomed"

    /// Shown once, never while scripting screenshots (`--demo`, `--section`) or after the user has seen it.
    static func shouldShow(welcomed: Bool, arguments: [String] = CommandLine.arguments) -> Bool {
        if arguments.contains("--welcome") { return true }   // forces the sheet (screenshots, QA)
        if welcomed { return false }
        return !arguments.contains("--demo") && !arguments.contains("--section") && !arguments.contains("--no-welcome")
    }
}

/// Fixed-size ring buffer of recent values per key (per-app and per-flow sparklines).
struct RateHistory {
    private(set) var series: [String: [Double]] = [:]
    let capacity: Int

    init(capacity: Int = 60) { self.capacity = capacity }

    /// Appends one sample per live key and drops keys that disappeared.
    mutating func record(_ values: [String: Double]) {
        for (k, v) in values {
            series[k, default: []].append(v)
            if series[k]!.count > capacity { series[k]!.removeFirst(series[k]!.count - capacity) }
        }
        for k in series.keys where values[k] == nil { series[k] = nil }
    }

    subscript(key: String) -> [Double] { series[key] ?? [] }
}
