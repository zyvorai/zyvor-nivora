// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

struct RootView: View {
    @EnvironmentObject var store: NivoraStore
    @EnvironmentObject var filter: NivoraFilterManager
    @State private var section: Pane?
    @State private var showWelcome = WelcomeGate.shouldShow(welcomed: UserDefaults.standard.bool(forKey: WelcomeGate.defaultsKey))
    @State private var showShortcuts = false

    var body: some View {
        NavigationSplitView {
            List(selection: $section) {
                ForEach(PaneSection.allCases) { group in
                    Section(group.rawValue) {
                        ForEach(Pane.allCases.filter { $0.section == group }) { pane in
                            HStack {
                                Label(pane.rawValue, systemImage: pane.symbol)
                                Spacer(minLength: 0)
                                if pane == .alerts, !store.alerts.isEmpty {
                                    Text("\(store.alerts.count)").font(.caption.weight(.semibold)).monospacedDigit()
                                        .foregroundStyle(Palette.textSecondary)
                                        .accessibilityLabel("\(store.alerts.count) active")
                                }
                            }.tag(pane)
                        }
                    }
                }
            }
            .navigationSplitViewColumnWidth(min: 190, ideal: 220, max: 260)
            .safeAreaInset(edge: .bottom) { HostFooter().padding(12) }
        } detail: {
            Group {
                if case .failed(let message) = store.status, store.snapshot == nil {
                    ContentUnavailableView {
                        Label("Collector unavailable", systemImage: "network.slash")
                    } description: { Text(message) } actions: {
                        Button("Try again") { Task { await store.refresh() } }
                    }
                } else if store.snapshot == nil {
                    ProgressView("Starting Nivora…").frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    switch section ?? .overview {
                    case .overview: OverviewView(open: { section = $0 })
                    case .health: HealthView()
                    case .applications: ApplicationsView()
                    case .flows: FlowsView()
                    case .timeline: TimelineView()
                    case .interfaces: InterfacesView()
                    case .local: LocalNetworkView()
                    case .fluxvm: FluxVMView()
                    case .security: SecurityView()
                    case .insights: InsightsView()
                    case .capture: CaptureView()
                    case .investigator: InvestigatorView()
                    case .alerts: AlertsView()
                    case .settings: SettingsView()
                    }
                }
            }
            .navigationTitle((section ?? .overview).rawValue)
            .navigationSubtitle(subtitle)
        }
        .searchable(text: $store.search, placement: .toolbar, prompt: "Search app, host, IP, port")
        .toolbar {
            ToolbarItemGroup {
                Button { store.paused.toggle() } label: { Image(systemName: store.paused ? "play.fill" : "pause.fill") }
                    .help(store.paused ? "Resume sampling" : "Pause sampling")
                Button { Task { await store.refresh() } } label: { Image(systemName: "arrow.clockwise") }.help("Refresh")
            }
        }
        .sheet(item: Binding(get: { store.selectedApp.map(AppSelection.init) }, set: { store.selectedApp = $0?.name })) { sel in
            AppDetailSheet(name: sel.name)
        }
        .sheet(item: Binding(get: { store.selectedFlow.map(FlowSelection.init) }, set: { store.selectedFlow = $0?.id })) { sel in
            FlowDetailSheet(flowID: sel.id)
        }
        .sheet(isPresented: $showWelcome) { WelcomeView() }
        .sheet(isPresented: $showShortcuts) { ShortcutsView() }
        .onReceive(NotificationCenter.default.publisher(for: .nivoraShowShortcuts)) { _ in showShortcuts = true }
        .task { await filter.load() }
        .onAppear { if section == nil { section = store.pane ?? .overview } }
        // Keep the sidebar selection and the persisted/menu-driven pane in sync without recreating bindings.
        .onChange(of: section) { _, new in if store.pane != new { store.pane = new } }
        .onChange(of: store.pane) { _, new in if section != new { section = new } }
    }

    private var subtitle: String {
        guard let s = store.snapshot else { return "" }
        return "\(s.host.name) · \(s.host.demo ? "Simulated telemetry" : "Live telemetry")"
    }
}

struct AppSelection: Identifiable { let name: String; var id: String { name } }

struct HostFooter: View {
    @EnvironmentObject var store: NivoraStore
    @EnvironmentObject var filter: NivoraFilterManager
    var body: some View {
        HStack(spacing: 8) {
            Circle().fill(color).frame(width: 8, height: 8)
            VStack(alignment: .leading, spacing: 1) {
                Text(store.snapshot?.host.name ?? "Nivora").font(.callout.weight(.medium)).lineLimit(1)
                Text(label).font(.caption).foregroundStyle(Palette.textSecondary).lineLimit(1)
            }
            Spacer(minLength: 0)
        }
    }
    private var color: Color {
        switch store.status { case .live: return store.paused ? Palette.amber : Palette.green; case .starting: return Palette.amber; case .failed: return Palette.danger }
    }
    private var label: String {
        if store.paused { return "Paused" }
        switch store.status {
        case .starting: return "Starting…"
        case .failed: return "Disconnected"
        case .live: return store.snapshot?.host.demo == true ? "Simulated · \(filter.status)" : filter.status
        }
    }
}

struct FlowSelection: Identifiable { let id: String }

extension Notification.Name { static let nivoraShowShortcuts = Notification.Name("nivora.showShortcuts") }
