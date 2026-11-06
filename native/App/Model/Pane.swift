// SPDX-License-Identifier: BUSL-1.1
import Foundation

enum PaneSection: String, CaseIterable, Identifiable {
    case monitor = "Monitor", network = "Network", zyvor = "Zyvor", system = "System"
    var id: Self { self }
}

enum Pane: String, CaseIterable, Identifiable {
    case overview = "Overview", health = "Health", applications = "Applications", flows = "Flows", timeline = "Time Machine"
    case map = "Network Map", domains = "Domains"
    case interfaces = "Interfaces", local = "Local Network", dns = "DNS", routes = "Routes", vpn = "VPN"
    case fluxvm = "FluxVM", security = "Security", insights = "Insights", capture = "Capture", investigator = "Investigator"
    case alerts = "Alerts", settings = "Settings"
    var id: Self { self }
    var section: PaneSection {
        switch self {
        case .overview, .health, .applications, .flows, .timeline, .map, .domains: return .monitor
        case .interfaces, .local, .dns, .routes, .vpn: return .network
        case .fluxvm, .security, .insights, .capture, .investigator: return .zyvor
        case .alerts, .settings: return .system
        }
    }
    var symbol: String {
        switch self {
        case .overview: return "gauge.with.dots.needle.bottom.50percent"
        case .health: return "heart.text.square"
        case .applications: return "square.stack.3d.up"
        case .flows: return "arrow.left.arrow.right"
        case .timeline: return "clock.arrow.circlepath"
        case .map: return "point.3.connected.trianglepath.dotted"
        case .domains: return "globe"
        case .dns: return "server.rack"
        case .routes: return "arrow.triangle.branch"
        case .vpn: return "lock.icloud"
        case .interfaces: return "network"
        case .local: return "macwindow.on.rectangle"
        case .fluxvm: return "shippingbox"
        case .security: return "lock.shield"
        case .insights: return "checkmark.shield"
        case .capture: return "record.circle"
        case .investigator: return "sparkles"
        case .alerts: return "bell.badge"
        case .settings: return "gearshape"
        }
    }
    var subtitle: String {
        switch self {
        case .overview: return "What is talking to what, through which network"
        case .health: return "Route, DNS, latency, interfaces and safety"
        case .applications: return "Every app, its connections and traffic"
        case .flows: return "Live TCP and UDP conversations"
        case .timeline: return "What changed on this Mac's network, and when"
        case .map: return "Applications, interfaces and destinations in one topology"
        case .domains: return "Where your applications are connecting"
        case .dns: return "Resolvers and DNS context reported by macOS"
        case .routes: return "Default gateways and the active routing table"
        case .vpn: return "Configured and active macOS network connections"
        case .interfaces: return "Wi‑Fi, Ethernet, VPN and virtual interfaces"
        case .local: return "Neighbors, listeners and exposure"
        case .fluxvm: return "VMs and sandboxes beside host traffic"
        case .security: return "Observe-first findings and rules"
        case .insights: return "Trust, privacy, situation profiles and egress"
        case .capture: return "Opt-in, headers-only packet capture"
        case .investigator: return "Ask the local telemetry"
        case .alerts: return "Findings and threshold checks"
        case .settings: return "Appearance, alerts and data"
        }
    }
}
