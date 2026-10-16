// SPDX-License-Identifier: BUSL-1.1
import Foundation

/// The bundled collector needs a couple of seconds to start listening, and the app polls it immediately, so a
/// failed poll that early is startup, not an error. Only after the grace period without any data is it reported.
enum CollectorStartup {
    static let grace: TimeInterval = 20

    enum Outcome: Equatable {
        case keep               // data is already on screen: leave it
        case starting           // still within the grace period: keep showing "Starting Nivora…"
        case failed(String)     // no data after the grace period: show the error
    }

    static func outcome(hasSnapshot: Bool, sinceStart: TimeInterval, message: String) -> Outcome {
        if hasSnapshot { return .keep }
        return sinceStart < grace ? .starting : .failed(message)
    }
}
