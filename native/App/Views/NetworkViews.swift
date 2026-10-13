// SPDX-License-Identifier: BUSL-1.1
import SwiftUI

struct InterfacesView: View {
    @EnvironmentObject var store: NivoraStore
    var body: some View {
        if let s = store.snapshot {
            Page {
                if let w = s.wifi?.ssid {
                    Panel(title: "Wi‑Fi") { LabeledContent("Network", value: w); LabeledContent("Interface", value: s.wifi?.interface ?? "—") }
                }
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 280), spacing: 16)], spacing: 16) {
                    ForEach(s.interfaces) { i in
                        Panel(title: i.name) {
                            HStack { StatusPill(text: i.status.capitalized, kind: i.status); StatusPill(text: i.kind, kind: "neutral") }
                            LabeledContent("IPv4", value: i.ipv4.joined(separator: ", ").isEmpty ? "—" : i.ipv4.joined(separator: ", "))
                            LabeledContent("IPv6", value: i.ipv6.first ?? "—")
                            LabeledContent("MTU", value: "\(i.mtu)")
                            LabeledContent("MAC", value: i.mac.isEmpty ? "—" : i.mac)
                        }
                    }
                }
                if let routes = s.routes, !routes.isEmpty {
                    Panel(title: "Routes") {
                        ForEach(routes.prefix(12)) { r in
                            HStack { Text(r.default ? "default" : r.destination).font(.system(.callout, design: .monospaced)); Spacer()
                                Text(r.gateway).foregroundStyle(Palette.textSecondary); StatusPill(text: r.interface, kind: "neutral") }
                        }
                    }
                }
                Panel(title: "DNS & VPN") {
                    LabeledContent("Resolvers", value: s.dns.servers.joined(separator: ", ").isEmpty ? "—" : s.dns.servers.joined(separator: ", "))
                    ForEach(s.vpn) { v in LabeledContent(v.name) { StatusPill(text: v.active ? "Active" : v.status, kind: v.active ? "active" : "neutral") } }
                }
            }
        }
    }
}

struct LocalNetworkView: View {
    @EnvironmentObject var store: NivoraStore
    var body: some View {
        if let s = store.snapshot {
            Page {
                HStack(alignment: .top, spacing: 16) {
                    Panel(title: "Neighbors", subtitle: "ARP + NDP cache") {
                        ForEach(s.neighbors) { n in
                            HStack { Text(n.ip).font(.system(.callout, design: .monospaced)); Spacer(); Text(n.mac).font(.caption).foregroundStyle(Palette.textSecondary); StatusPill(text: n.interface, kind: "neutral") }
                        }
                        if s.neighbors.isEmpty { Text("No neighbors reported.").foregroundStyle(Palette.textSecondary) }
                    }
                    Panel(title: "Listening services", subtitle: "Bound to all interfaces is shown in amber") {
                        ForEach(s.listeners) { l in
                            HStack { Text(l.process).fontWeight(.medium); Text("\(l.address):\(l.port)").font(.system(.callout, design: .monospaced)).foregroundStyle(Palette.textSecondary)
                                Spacer(); StatusPill(text: l.exposure.capitalized, kind: l.exposure) }
                        }
                        if s.listeners.isEmpty { Text("No listeners reported.").foregroundStyle(Palette.textSecondary) }
                    }
                }
            }
        }
    }
}

struct FluxVMView: View {
    @EnvironmentObject var store: NivoraStore
    var body: some View {
        if let s = store.snapshot {
            let f = s.fluxvm
            Page {
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: 3), spacing: 12) {
                    MetricTile(label: "FluxVM", symbol: "shippingbox", value: f?.connected == true ? "Connected" : "Not detected", hint: f?.base_url ?? "http://127.0.0.1:7788")
                    MetricTile(label: "VMs", symbol: "desktopcomputer", value: "\(f?.vms?.count ?? 0)", hint: "reported by local API")
                    MetricTile(label: "Sandboxes", symbol: "cube", value: "\(f?.sandboxes?.count ?? 0)", hint: "reported by local API")
                }
                Panel(title: "Compute") {
                    let all = (f?.vms ?? []) + (f?.sandboxes ?? [])
                    ForEach(all) { w in
                        HStack { Text(w.ident ?? "workload").fontWeight(.medium); Spacer(); StatusPill(text: (w.state ?? w.backend ?? "reported").capitalized, kind: w.state ?? "neutral") }
                    }
                    if all.isEmpty { Text("Start FluxVM locally or set FLUXVM_SERVER. Nivora probes health, VMs, sandboxes and network telemetry.").foregroundStyle(Palette.textSecondary) }
                }
            }
        }
    }
}
