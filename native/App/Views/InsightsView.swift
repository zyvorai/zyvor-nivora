// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

/// Trust, privacy, situation profile and sandbox egress. Everything here is derived from local telemetry.
struct InsightsView: View {
    @EnvironmentObject var store: NivoraStore
    private let profiles = [("default", "Default"), ("coding", "Coding"), ("presenting", "Presenting"), ("travel", "Travel / hotspot")]

    var body: some View {
        if let s = store.snapshot {
            Page {
                Panel(title: "Situation profile", subtitle: "Changes alert thresholds and what is shown. Never relaxes blocking rules or leases.") {
                    Picker("Profile", selection: Binding(get: { s.profile?.name ?? "default" }, set: { v in Task { await store.setProfile(v) } })) {
                        ForEach(profiles, id: \.0) { Text($0.1).tag($0.0) }
                    }.pickerStyle(.segmented)
                }
                if let p = s.privacy {
                    Panel(title: "Privacy report card", subtitle: "Score \(p.score) / 100") {
                        if p.trackers.isEmpty && p.cleartext.isEmpty && !p.dns_vpn_leak {
                            Text("No known trackers, cleartext protocols or DNS leaks seen.").foregroundStyle(Palette.textSecondary)
                        }
                        ForEach(p.trackers) { t in
                            HStack { Text(t.app); Text(t.host).font(.caption.monospaced()).foregroundStyle(Palette.textSecondary); Spacer(); StatusPill(text: t.category, kind: "warning") }
                        }
                        ForEach(p.cleartext) { c in
                            HStack { Text(c.app); Text("\(c.host):\(c.port)").font(.caption.monospaced()).foregroundStyle(Palette.textSecondary); Spacer(); StatusPill(text: c.protocol, kind: "critical") }
                        }
                        if p.dns_vpn_leak { Label("DNS may bypass the VPN", systemImage: "exclamationmark.triangle").foregroundStyle(Palette.danger) }
                        ForEach(p.notes, id: \.self) { Text($0).font(.caption).foregroundStyle(Palette.textSecondary) }
                    }
                }
                Panel(title: "Trust by app", subtitle: "Every point is attributed to a visible check") {
                    let rows = Array((s.trust ?? []).prefix(15))
                    if rows.isEmpty { Text("No apps yet.").foregroundStyle(Palette.textSecondary) }
                    ForEach(rows) { t in
                        DisclosureGroup {
                            ForEach(t.components) { c in
                                HStack(alignment: .top) {
                                    Text("\(c.name)").frame(width: 170, alignment: .leading)
                                    Text("\(c.points)/\(c.max)").monospacedDigit().foregroundStyle(c.points < c.max ? Palette.amber : Palette.green)
                                    Text(c.detail).font(.caption).foregroundStyle(Palette.textSecondary)
                                }.font(.callout)
                            }
                        } label: {
                            HStack { Text(t.app); Spacer(); StatusPill(text: "\(t.level) · \(t.score)", kind: t.level == "high" ? "good" : t.level == "low" ? "critical" : "warning") }
                        }
                    }
                }
                if let e = s.egress {
                    Panel(title: "Sandbox and VM egress", subtitle: "From FluxVM network data") {
                        if !e.connected { Text(e.note ?? "FluxVM is not connected.").foregroundStyle(Palette.textSecondary) }
                        else if e.workloads.isEmpty { Text("No workload traffic reported.").foregroundStyle(Palette.textSecondary) }
                        ForEach(e.workloads) { w in
                            HStack { Text(w.ident); Text(w.kind).font(.caption).foregroundStyle(Palette.textSecondary); Spacer()
                                Text("\(w.external) external · \(w.destinations.count) destinations").font(.callout).foregroundStyle(Palette.textSecondary) }
                        }
                    }
                }
            }
        }
    }
}
