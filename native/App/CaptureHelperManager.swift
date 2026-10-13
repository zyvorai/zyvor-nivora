// SPDX-License-Identifier: BUSL-1.1
import AppKit
import ServiceManagement

/// Registers the privileged capture helper as a launchd daemon through SMAppService.
/// Registration needs a signed build and explicit approval in System Settings > Login Items;
/// this path is compile-verified only.
@MainActor
final class CaptureHelperManager: ObservableObject {
    static let plistName = "dev.zyvor.nivora.capture-helper.plist"
    @Published private(set) var status: SMAppService.Status = .notRegistered
    @Published var message: String?

    private var service: SMAppService { SMAppService.daemon(plistName: Self.plistName) }

    func refresh() { status = service.status }

    var label: String {
        switch status {
        case .enabled: return "Helper approved"
        case .requiresApproval: return "Waiting for approval in System Settings"
        case .notFound: return "Helper not bundled in this build"
        default: return "Helper not installed"
        }
    }

    func install() {
        do {
            try service.register()
            message = nil
        } catch {
            message = "Could not register the helper: \(error.localizedDescription). A signed build is required."
        }
        refresh()
        if status == .requiresApproval { SMAppService.openSystemSettingsLoginItems() }
    }

    func uninstall() {
        do { try service.unregister(); message = nil } catch { message = error.localizedDescription }
        refresh()
    }
}
