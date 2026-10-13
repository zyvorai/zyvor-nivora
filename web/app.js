// SPDX-License-Identifier: BUSL-1.1
const $ = (q) => document.querySelector(q);
const $$ = (q) => [...document.querySelectorAll(q)];
import {ACCENTS,esc,fmtBytes,fmtRate,hostOf,portOf,initials,matchQuery,filterFlows,filterChips,dropFilterChip,sortRows,scoreStatus,sparklinePath,flowsToCSV,mergePrefs,pushSample,highlight,rateAlerts} from '/lib.js';
const PREF_KEY='nivora-prefs';
const state = { token: '', snapshot: null, view: 'overview', paused: false, timer: null, search: '', sort: {applications:{key:'total_bps',dir:'desc'},flows:{key:'rx_bps',dir:'desc'}}, samples: {}, prefs: mergePrefs(null), error: '', updatedAt: 0, alerted: new Set(), sheetApp: null, goto: false };
try{state.prefs=mergePrefs(localStorage.getItem(PREF_KEY))}catch{}
function savePrefs(){try{localStorage.setItem(PREF_KEY,JSON.stringify(state.prefs))}catch{}applyPrefs()}
function applyPrefs(){
  const p=state.prefs,r=document.documentElement;
  if(p.appearance==='auto')delete r.dataset.theme;else r.dataset.theme=p.appearance;
  r.dataset.density=p.density;r.classList.toggle('reduce-glass',p.reduceTransparency);
  if(p.accent==='blue')r.style.removeProperty('--blue');else r.style.setProperty('--blue',ACCENTS[p.accent]);
  if(state.timer)clearInterval(state.timer);
  state.timer=setInterval(refresh,p.refreshMs);
}
function toast(msg,kind=''){const el=document.createElement('div');el.className=`toast ${kind}`;el.textContent=msg;$('#toasts').append(el);setTimeout(()=>el.remove(),kind==='error'?6000:3500)}

const titles = {
  overview:['Monitor','Overview','What is talking to what, through which network.'], health:['Diagnose','Health','A live score for route, DNS, latency, interfaces and safety.'], map:['Monitor','Network Map','Applications, interfaces and destinations in one topology.'], applications:['Workloads','Applications','Every app, its connections, destinations and traffic.'], flows:['Monitor','Flows','Live TCP and UDP conversations observed on this Mac.'], domains:['Monitor','Domains','Where your applications are connecting.'], dns:['Network','DNS','Resolvers and DNS context reported by macOS.'], interfaces:['Network','Interfaces','Wi‑Fi, Ethernet, VPN, bridge and virtual interfaces.'], routes:['Network','Routes','Default gateways and the active routing table.'], vpn:['Network','VPN','Configured and active macOS network connections.'], local:['Network','Local Network','Neighbors, listening services and exposure on this Mac.'], fluxvm:['Zyvor','FluxVM','VMs and sandboxes correlated with host network activity.'], security:['Protect','Security','Observe-first findings and rule previews.'], timeline:['Diagnose','Network Time Machine','What changed, when it changed, and what happened next.'], investigator:['AI','Investigator','Ask the local telemetry a question. No cloud required.'], settings:['System','Settings','Appearance, refresh rate, alerts and pinned applications.']
};

function badge(text,kind=''){return `<span class="pill ${kind}">${esc(text)}</span>`}
function currentToken(){return state.token}
function authHeaders(extra={}){return {...extra,...(state.token?{Authorization:`Bearer ${state.token}`}:{})}}

async function api(path, opts={}){
  const r=await fetch(path,{...opts,headers:authHeaders({'Content-Type':'application/json',...(opts.headers||{})}),cache:'no-store'});
  if(r.status===401){showConnect(); throw new Error('Authentication required')}
  if(!r.ok)throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

function showConnect(){const d=$('#connectDialog');if(!d.open)d.showModal()}
function parseToken(){const m=location.hash.match(/(?:^#|&)token=([^&]+)/);if(m){state.token=decodeURIComponent(m[1]);history.replaceState(null,'',location.pathname+location.search)}}

async function refresh(){
  if(state.paused)return;
  try{
    const snap=await api('/v1/snapshot'); state.snapshot=snap; state.error=''; state.updatedAt=Date.now();
    for(const ap of snap.apps||[])pushSample(state.samples,ap.name,ap.total_bps||((ap.rx_bps||0)+(ap.tx_bps||0)));
    pushSample(state.samples,'__total',snap.traffic?.total_bps||0);
    setLive(true); checkAlerts(snap); render({tick:true});
    $('#hostName').textContent=snap.host?.name||'This Mac'; $('#hostMeta').textContent=`${snap.host?.os||''} ${snap.host?.release||''} · ${snap.host?.arch||''}`;
  }catch(e){if(!String(e).includes('Authentication')){state.error=String(e.message||e);setLive(false,'Disconnected — retrying');if(!state.snapshot)render()}}
}
function checkAlerts(snap){
  const hits=rateAlerts(snap.apps,state.prefs.alertMbps),badgeEl=$('#alertBadge');
  badgeEl.hidden=!hits.length;badgeEl.textContent=hits.length;
  for(const h of hits)if(!state.alerted.has(h.app)){state.alerted.add(h.app);toast(`${h.app} is above ${state.prefs.alertMbps} Mbit/s (${fmtRate(h.bps)}). Observing only.`,'warn')}
  for(const k of [...state.alerted])if(!hits.some(h=>h.app===k))state.alerted.delete(k);
}
function setLive(ok,label){$('#liveDot').classList.toggle('live',ok);$('#liveLabel').textContent=label||(ok?(state.snapshot?.host?.demo?'Simulated telemetry':'Live telemetry'):'Disconnected')}

function setView(v){state.view=v;$$('#nav button').forEach(b=>b.classList.toggle('active',b.dataset.view===v));const [e,t,s]=titles[v]||titles.overview;$('#eyebrow').textContent=e;$('#viewTitle').textContent=t;$('#viewSubtitle').textContent=s;render()}
function filteredFlows(){const s=state.snapshot;return s?filterFlows(s.flows||[],state.search):[]}
function filteredApps(){const s=state.snapshot;if(!s)return[];const by=new Map((s.apps||[]).map(a=>[a.name,a]));
  // apps reuse the flow grammar through a flow-shaped projection
  return filterFlows((s.apps||[]).map(a=>({...a,process:a.name,remote:(a.domains||[])[0]||'',interface:(a.interfaces||[])[0]||''})),state.search).map(a=>by.get(a.name))}
function filterBar(){
  const chips=filterChips(state.search),views=state.prefs.views||[];
  return `<div class="filter-bar"><div class="chips">${chips.map((c,i)=>`<button class="chip" data-chip="${i}" aria-label="Remove filter ${esc(c)}">${esc(c)} <span aria-hidden="true">×</span></button>`).join('')||'<span class="muted">Type to filter: app:Safari port:443 proto:tcp &gt;1mbps !iface:lo0</span>'}</div><div class="views">${views.map((v,i)=>`<span class="view-pill"><button data-view-q="${i}">${esc(v.name)}</button><button data-view-del="${i}" aria-label="Delete view ${esc(v.name)}">×</button></span>`).join('')}<button id="saveViewBtn" class="glass-btn" ${chips.length?'':'disabled'}>Save view</button></div></div>`}
function th(view,key,label){const so=state.sort[view];return `<th data-sort="${key}" data-view="${view}" aria-sort="${so.key===key?(so.dir==='asc'?'ascending':'descending'):'none'}" tabindex="0">${label}</th>`}

function stat(label,value,sub=''){return `<div class="card stat"><small>${esc(label)}</small><strong>${esc(value)}</strong><span>${esc(sub)}</span></div>`}
function appTable(apps){
  const so=state.sort.applications,pins=state.prefs.pinned;
  const rows=sortRows(sortRows(apps,so.key,so.dir),a=>pins.includes(a.name)?0:1,'asc');
  return `<div class="table-wrap"><table><thead><tr><th></th>${th('applications','name','Application')}${th('applications','connections','Connections')}${th('applications','rx_bps','↓ Live')}${th('applications','tx_bps','↑ Live')}${th('applications','bytes_in','Received')}${th('applications','bytes_out','Sent')}<th>Destinations</th></tr></thead><tbody>${rows.map(a=>`<tr class="clickable" data-app="${esc(a.name)}"><td><button class="pin ${pins.includes(a.name)?'on':''}" data-pin="${esc(a.name)}" aria-label="Pin ${esc(a.name)}" aria-pressed="${pins.includes(a.name)}">★</button></td><td><div class="app-cell"><div class="app-icon">${esc(initials(a.name))}</div><div><strong>${highlight(a.name,state.search)}</strong><div class="muted mono">${a.pid||''}</div></div></div></td><td>${a.connections}</td><td>${fmtRate(a.rx_bps||0)}</td><td>${fmtRate(a.tx_bps||0)}</td><td>${fmtBytes(a.bytes_in)}</td><td>${fmtBytes(a.bytes_out)}</td><td>${(a.domains||[]).slice(0,2).map(x=>badge(x)).join(' ')||'—'}</td></tr>`).join('')||`<tr><td colspan="8"><div class="empty">${state.search?'No applications match your search.':'No application traffic yet.'}</div></td></tr>`}</tbody></table></div>`}
function flowTable(flows,sortable=true){
  const so=state.sort.flows,rows=sortable?sortRows(flows,so.key,so.dir):flows,h=(k,l)=>sortable?th('flows',k,l):`<th>${l}</th>`;
  return `<div class="table-wrap"><table><thead><tr>${h('process','App')}${h('protocol','Proto')}${h('remote','Remote')}${h('state','State')}${h('interface','Interface')}${h('rtt_ms','RTT')}${h('rx_bps','↓ Live')}${h('tx_bps','↑ Live')}${h('bytes_in','↓')}${h('bytes_out','↑')}</tr></thead><tbody>${rows.map(f=>`<tr><td><div class="app-cell"><div class="app-icon">${esc(initials(f.process))}</div>${highlight(f.process||'Unknown',state.search)}</div></td><td>${badge((f.protocol||'—').toUpperCase())}</td><td class="mono">${highlight(f.remote||'—',state.search)}</td><td>${esc(f.state||'—')}</td><td>${badge(f.interface||'—')}</td><td>${f.rtt_ms?`${Number(f.rtt_ms).toFixed(1)} ms`:'—'}</td><td>${fmtRate(f.rx_bps||0)}</td><td>${fmtRate(f.tx_bps||0)}</td><td>${fmtBytes(f.bytes_in)}</td><td>${fmtBytes(f.bytes_out)}</td></tr>`).join('')||`<tr><td colspan="10"><div class="empty">${state.search?'No flows match your search.':'No flows in the current sample.'}</div></td></tr>`}</tbody></table></div>`}
function findingsList(fs){return fs.length?fs.map(f=>`<div class="finding"><i class="severity ${esc(f.severity)}"></i><div><strong>${esc(f.title)}</strong><p>${esc(f.detail)}</p></div></div>`).join(''):`<div class="empty">No current findings.<br>Observe-first mode is quiet.</div>`}

function overview(s){
  const flows=filteredFlows(), apps=filteredApps(), t=s.traffic||{}, h=s.health||{};
  const top=apps.slice().sort((a,b)=>(b.total_bps||0)-(a.total_bps||0)||(b.total_bytes||0)-(a.total_bytes||0)).slice(0,6), max=Math.max(1,...top.map(a=>a.total_bps||a.total_bytes||0));
  const interfaces=(s.interfaces||[]).filter(i=>i.status==='active'||(i.flags||[]).includes('UP'));
  const talkers=apps.slice().sort((a,b)=>(b.total_bps||0)-(a.total_bps||0)).slice(0,3);
  return `<div class="grid stats">${stat('Health',`${h.score??'—'}/100`,h.status||'unknown')}${stat('Download',fmtRate(t.rx_bps||0),'live')}${stat('Upload',fmtRate(t.tx_bps||0),'live')}${stat('Connections',flows.length,`${apps.length} applications`)}</div>
  <div class="card" style="margin-bottom:14px"><h2>Throughput</h2><div id="overviewChart" class="chart-wrap"><div class="skeleton"></div></div></div>
  <div class="talkers">${talkers.map(a=>`<div class="card talker" data-app="${esc(a.name)}"><small class="muted">Top talker</small><strong>${esc(a.name)}</strong><svg viewBox="0 0 120 32" preserveAspectRatio="none" aria-hidden="true"><path d="${sparklinePath(state.samples[a.name],120,32)}"/></svg><span class="muted">${fmtRate(a.total_bps||0)}</span></div>`).join('')}</div>
  <div class="split"><div class="card"><h2>Live application traffic</h2>${top.map(a=>`<div class="bar-row"><span>${esc(a.name)}</span><div class="bar"><i style="width:${Math.max(2,(a.total_bps||a.total_bytes||0)/max*100)}%"></i></div><strong>${a.total_bps?fmtRate(a.total_bps):fmtBytes(a.total_bytes)}</strong></div>`).join('')||'<div class="empty">No app traffic yet</div>'}</div><div class="card"><h2>Network health</h2><div class="health-inline"><div class="score-ring ${esc(scoreStatus(h.score))}" style="--score:${Number(h.score)||0}"><strong>${h.score??'—'}</strong><span>/100</span></div><div>${(h.components||[]).map(c=>`<div class="component"><span>${esc(c.name)}</span><div class="mini-bar"><i style="width:${Number(c.score||0)}%"></i></div><small>${esc(c.detail||'')}</small></div>`).join('')}</div></div></div></div>
  <div class="split" style="margin-top:14px"><div class="card"><h2>What needs attention</h2>${findingsList((s.findings||[]).slice(0,6))}</div><div class="card"><h2>Active path</h2><div class="metric-inline"><span>Wi‑Fi</span><span>${esc(s.wifi?.ssid||'not reported')}</span></div><div class="metric-inline"><span>Primary interface</span><span>${esc(t.top_interface||interfaces[0]?.name||'—')}</span></div><div class="metric-inline"><span>VPN flows</span><span>${t.vpn_flows||0}</span></div><div class="metric-inline"><span>FluxVM</span><span>${s.fluxvm?.connected?'connected':'not detected'}</span></div></div></div>`;
}
function health(s){const h=s.health||{},d=s.diagnosis||{};return `<div class="grid stats">${stat('Health score',`${h.score??'—'}/100`,h.status||'unknown')}${stat('Median RTT',`${h.median_rtt_ms||0} ms`,'observed flows')}${stat('New destinations',(s.behavior?.new_destinations||[]).length,`${s.behavior?.known_destinations||0} learned`)}${stat('Findings',(s.findings||[]).length,'current')}</div><div class="split"><div class="card"><h2>Health components</h2>${(h.components||[]).map(c=>`<div class="health-row"><div><strong>${esc(c.name)}</strong><small>${esc(c.detail||'')}</small></div><div class="health-meter"><i style="width:${c.score||0}%"></i></div><b>${c.score||0}</b></div>`).join('')}</div><div class="card"><h2>Diagnosis</h2><div class="diagnosis"><strong>${esc(d.summary||'No diagnosis yet.')}</strong>${(d.causes||[]).map(c=>`<div class="finding"><i class="severity ${esc(c.severity||'info')}"></i><div><strong>${esc(c.title)}</strong><p>${esc(c.detail)}</p></div></div>`).join('')||'<p class="muted">No likely fault is visible in the current telemetry.</p>'}</div></div></div><div class="card" style="margin-top:14px"><h2>Traffic history</h2><div id="seriesBody" class="spark-bars"><div class="empty">Loading history…</div></div></div>`}
function networkMap(s){const t=s.topology||{},nodes=t.nodes||[],edges=t.edges||[];const apps=nodes.filter(n=>n.kind==='app').slice(0,10),ifs=nodes.filter(n=>n.kind==='interface'),dst=nodes.filter(n=>['domain','internet','local','loopback'].includes(n.kind)).slice(0,14);const count=(id,side)=>edges.filter(e=>e[side]===id).reduce((n,e)=>n+(e.flows||0),0);return `<div class="grid stats">${stat('Nodes',nodes.length,'topology objects')}${stat('Edges',edges.length,'observed relationships')}${stat('Applications',apps.length,'shown')}${stat('Destinations',dst.length,'top traffic')}</div><div class="network-map"><div class="map-column"><h3>Applications</h3>${apps.map(n=>`<div class="map-chip app"><strong>${esc(n.label)}</strong><small>${count(n.id,'source')} paths</small></div>`).join('')}</div><div class="map-arrow">→</div><div class="map-column"><h3>This Mac</h3><div class="map-chip host"><strong>${esc(s.host?.name||'This Mac')}</strong><small>${esc(s.wifi?.ssid||'macOS')}</small></div>${ifs.map(n=>`<div class="map-chip iface"><strong>${esc(n.label||'unknown')}</strong><small>${count(n.id,'target')} app edges · ${count(n.id,'source')} destinations</small></div>`).join('')}</div><div class="map-arrow">→</div><div class="map-column"><h3>Destinations</h3>${dst.map(n=>`<div class="map-chip dst"><strong>${esc(n.label)}</strong><small>${esc(n.kind)}</small></div>`).join('')}</div></div>`}

function applications(s){const a=filteredApps();return `<div class="grid stats">${stat('Apps',a.length,'network-active')}${stat('Top sender',a.slice().sort((x,y)=>(y.tx_bps||0)-(x.tx_bps||0))[0]?.name||'—',fmtRate(a.slice().sort((x,y)=>(y.tx_bps||0)-(x.tx_bps||0))[0]?.tx_bps||0))}${stat('Top receiver',a.slice().sort((x,y)=>(y.rx_bps||0)-(x.rx_bps||0))[0]?.name||'—',fmtRate(a.slice().sort((x,y)=>(y.rx_bps||0)-(x.rx_bps||0))[0]?.rx_bps||0))}${stat('Internet apps',a.filter(x=>x.internet_connections).length,'public destinations')}</div><div class="card"><h2>Applications</h2>${appTable(a)}</div>`}
function flows(s){const f=filteredFlows();return `<div class="grid stats">${stat('Flows',f.length,'observed now')}${stat('TCP',f.filter(x=>x.protocol==='tcp').length,'connections')}${stat('UDP',f.filter(x=>x.protocol==='udp').length,'flows')}${stat('High RTT',f.filter(x=>(x.rtt_ms||0)>150).length,'over 150 ms')}</div><div class="card"><h2>Live flows</h2>${filterBar()}${flowTable(f)}</div>`}
function domains(s){const c=new Map();for(const f of filteredFlows()){const h=hostOf(f.remote);if(!h)continue;const o=c.get(h)||{host:h,flows:0,bytes:0,apps:new Set(),ports:new Set()};o.flows++;o.bytes+=(f.bytes_in||0)+(f.bytes_out||0);o.apps.add(f.process);if(portOf(f.remote))o.ports.add(portOf(f.remote));c.set(h,o)}const arr=[...c.values()].sort((a,b)=>b.bytes-a.bytes);return `<div class="card"><h2>Destinations</h2><div class="table-wrap"><table><thead><tr><th>Host</th><th>Apps</th><th>Flows</th><th>Ports</th><th>Traffic</th></tr></thead><tbody>${arr.map(x=>`<tr><td class="mono">${esc(x.host)}</td><td>${[...x.apps].slice(0,3).map(a=>badge(a)).join(' ')}</td><td>${x.flows}</td><td>${[...x.ports].join(', ')||'—'}</td><td>${fmtBytes(x.bytes)}</td></tr>`).join('')}</tbody></table></div></div>`}
function dns(s){const d=s.dns||{};return `<div class="grid stats">${stat('Resolvers',(d.resolvers||[]).length,'scutil resolvers')}${stat('Nameservers',(d.servers||[]).length,(d.servers||[]).join(' · ')||'none')}${stat('VPN resolver',(d.resolvers||[]).filter(r=>String(r.interface||'').startsWith('utun')).length,'scoped to tunnel')}${stat('Search domains',[...new Set((d.resolvers||[]).flatMap(r=>r.search||[]))].length,'configured')}</div><div class="topology">${(d.resolvers||[]).map(r=>`<div class="card"><h2>Resolver ${r.index}</h2><div class="metric-inline"><span>Interface</span><span>${esc(r.interface||'default')}</span></div><div class="metric-inline"><span>Domain</span><span>${esc(r.domain||'default')}</span></div><div class="metric-inline"><span>Servers</span><span class="mono">${esc((r.nameservers||[]).join(', ')||'—')}</span></div></div>`).join('')||'<div class="card empty">No DNS resolver reported</div>'}</div>`}
function interfaces(s){return `<div class="topology">${(s.interfaces||[]).map(i=>`<div class="card"><h2>${esc(i.name)} ${badge(i.status||'unknown',i.status==='active'?'green':'')}</h2><div class="metric-inline"><span>Kind</span><span>${esc(i.kind)}</span></div><div class="metric-inline"><span>IPv4</span><span class="mono">${esc((i.ipv4||[]).join(', ')||'—')}</span></div><div class="metric-inline"><span>IPv6</span><span class="mono">${esc((i.ipv6||[]).join(', ')||'—')}</span></div><div class="metric-inline"><span>MTU</span><span>${i.mtu||'—'}</span></div><div class="metric-inline"><span>MAC</span><span class="mono">${esc(i.mac||'—')}</span></div></div>`).join('')||'<div class="card empty">No interfaces reported</div>'}</div>`}
function routes(s){return `<div class="card"><h2>Routing table</h2><div class="table-wrap"><table><thead><tr><th>Family</th><th>Destination</th><th>Gateway</th><th>Interface</th><th>Flags</th></tr></thead><tbody>${(s.routes||[]).map(r=>`<tr><td>${badge(r.family)}</td><td>${r.default?badge('default','green'):esc(r.destination)}</td><td class="mono">${esc(r.gateway)}</td><td>${esc(r.interface)}</td><td class="mono">${esc(r.flags)}</td></tr>`).join('')}</tbody></table></div></div>`}
function vpn(s){const active=(s.vpn||[]).filter(v=>v.active);const utun=(s.interfaces||[]).filter(i=>i.name.startsWith('utun'));return `<div class="grid stats">${stat('Active VPNs',active.length,active.map(x=>x.name).join(' · ')||'none')}${stat('Tunnel interfaces',utun.length,utun.map(x=>x.name).join(' · ')||'none')}${stat('Flows on VPN',(s.flows||[]).filter(f=>String(f.interface).startsWith('utun')).length,'observed')}${stat('VPN DNS',(s.dns?.resolvers||[]).filter(r=>String(r.interface).startsWith('utun')).length,'scoped resolvers')}</div><div class="topology">${(s.vpn||[]).map(v=>`<div class="card"><h2>${esc(v.name)} ${badge(v.active?'Active':v.status,v.active?'green':'')}</h2><div class="metric-inline"><span>Service</span><span class="mono">${esc(v.service_id)}</span></div><div class="metric-inline"><span>Status</span><span>${esc(v.status)}</span></div></div>`).join('')||'<div class="card empty">No configured VPN services reported by scutil.</div>'}</div>`}
function localNetwork(s){const n=s.neighbors||[],l=s.listeners||[],exposed=l.filter(x=>x.exposure==='all');return `<div class="grid stats">${stat('Neighbors',n.length,'ARP + NDP cache')}${stat('Listeners',l.length,'bound sockets')}${stat('Exposed',exposed.length,'all interfaces')}${stat('Wi‑Fi',s.wifi?.ssid||'—',s.wifi?.interface||'')}</div><div class="split"><div class="card"><h2>Local neighbors</h2><div class="table-wrap"><table><thead><tr><th>IP</th><th>MAC</th><th>Interface</th><th>Family</th></tr></thead><tbody>${n.map(x=>`<tr><td class="mono">${esc(x.ip)}</td><td class="mono">${esc(x.mac||'—')}</td><td>${esc(x.interface||'—')}</td><td>${badge(x.family||'')}</td></tr>`).join('')}</tbody></table></div></div><div class="card"><h2>Listening services</h2><div class="table-wrap"><table><thead><tr><th>App</th><th>Proto</th><th>Bind</th><th>Exposure</th></tr></thead><tbody>${l.map(x=>`<tr><td>${esc(x.process)}</td><td>${badge(String(x.protocol||'').toUpperCase())}</td><td class="mono">${esc(x.address||'*')}:${x.port}</td><td>${badge(x.exposure,x.exposure==='all'?'red':x.exposure==='loopback'?'green':'')}</td></tr>`).join('')}</tbody></table></div></div></div>`}
function fluxvm(s){const f=s.fluxvm||{};const vmArr=Array.isArray(f.vms)?f.vms:(f.vms?.items||[]), sb=Array.isArray(f.sandboxes)?f.sandboxes:(f.sandboxes?.items||[]);const ff=(s.flows||[]).filter(x=>String(x.process).toLowerCase().includes('flux'));return `<div class="grid stats">${stat('FluxVM',f.connected?'Connected':'Not detected',f.base_url||'')}${stat('VMs',vmArr.length,'reported by local API')}${stat('Sandboxes',sb.length,'reported by local API')}${stat('Host flows',f.host_flow_count??ff.length,'FluxVM process attributed')}${stat('Net endpoints',f.network_endpoint_count||0,`${f.hubble_flow_count||0} Hubble flows`)}</div><div class="split"><div class="card"><h2>Compute</h2>${[...vmArr,...sb].map(v=>`<div class="metric-inline"><span>${esc(v.id||v.name||'workload')}</span><span>${esc(v.state||v.status||v.backend||'reported')}</span></div>`).join('')||'<div class="empty">Start FluxVM locally or configure FLUXVM_SERVER.<br>Nivora probes health, VMs, sandboxes and the network health, endpoints, Hubble flows, observe state and optional richer telemetry.</div>'}</div><div class="card"><h2>FluxVM-attributed host flows</h2>${ff.length?flowTable(ff):'<div class="empty">No FluxVM process flows in the current sample.</div>'}</div></div>`}
function security(s){const hits=s.rule_hits||[], rules=s.rules||[];return `<div class="grid stats">${stat('Findings',(s.findings||[]).length,'current')}${stat('Rules',rules.length,'observe / allow / block')}${stat('Rule hits',hits.length,'previewed against live flows')}${stat('Mode',s.capabilities?.blocking?'Enforce capable':'Observe-first',s.capabilities?.network_extension?'NetworkExtension present':'collector only')}${stat('New destinations',(s.behavior?.new_destinations||[]).length,'since learned baseline')}</div><div class="split"><div class="card"><h2>Findings</h2>${findingsList(s.findings||[])}</div><div class="card"><h2>Rules</h2><div class="rule-form"><select id="ruleAction"><option value="observe">Observe</option><option value="block">Block (1h lease)</option><option value="allow">Allow</option></select><select id="ruleType"><option value="domain">Domain</option><option value="app">Application</option><option value="ip">IP</option><option value="port">Port</option></select><input id="ruleValue" placeholder="github.com"><button id="addRuleBtn" class="primary">Add</button></div><div id="rulesList">${rules.map(r=>`<div class="metric-inline"><span>${badge(r.action,r.action==='block'?'red':r.action==='allow'?'green':'')} ${esc(r.app||r.domain||r.ip||('port '+r.port)||'rule')} ${r.expires_at?`<small class="muted">until ${esc(new Date(r.expires_at).toLocaleTimeString())}</small>`:''}</span><button class="icon-btn delete-rule" data-id="${esc(r.id)}">×</button></div>`).join('')||'<div class="empty" style="min-height:120px">No rules yet.</div>'}</div></div></div>`}
function timeline(s){return `<div class="card"><h2>Network Time Machine</h2><div id="timelineBody" class="timeline"><div class="empty">Loading timeline…</div></div></div>`}
function investigator(s){return `<div class="card"><h2>Ask Nivora</h2><p class="muted">The built-in investigator reasons over local telemetry only. Try “which app uploaded the most?”, “what uses port 443?”, “is my VPN active?”, “why is the network slow?”, or “show FluxVM”.</p><div class="query-box"><input id="question" placeholder="Why is Slack slow?"/><button id="askBtn" class="primary">Ask</button></div><div id="answer" class="answer"><strong>Ready</strong><span class="muted">No telemetry leaves this Mac.</span></div></div>`}


function bindSecurity(){
  const add=$('#addRuleBtn');if(add)add.onclick=async()=>{const action=$('#ruleAction').value,type=$('#ruleType').value,value=$('#ruleValue').value.trim();if(!value)return;const body={action};body[type]=type==='port'?Number(value):value;try{await api('/v1/rules',{method:'POST',body:JSON.stringify(body)});toast(`Rule added: ${action} ${value}`,'ok');await refresh()}catch(e){toast(String(e.message||e),'error')}};
  $$('.delete-rule').forEach(b=>b.onclick=async()=>{try{await api('/v1/rules/'+encodeURIComponent(b.dataset.id),{method:'DELETE'});await refresh()}catch(e){toast(String(e.message||e),'error')}});
}

function settings(){
  const p=state.prefs,seg=(k,opts)=>`<div class="seg" role="radiogroup">${opts.map(([v,l])=>`<button role="radio" data-pref="${k}" data-value="${v}" aria-checked="${String(p[k])===String(v)}">${l}</button>`).join('')}</div>`;
  return `<div class="card"><h2>Appearance</h2>
  <div class="settings-row"><span>Theme</span>${seg('appearance',[['auto','Auto'],['light','Light'],['dark','Dark']])}</div>
  <div class="settings-row"><span>Accent</span><div>${Object.entries(ACCENTS).map(([k,c])=>`<button class="swatch" role="radio" aria-label="${k}" data-pref="accent" data-value="${k}" aria-checked="${p.accent===k}" style="background:${c}"></button>`).join(' ')}</div></div>
  <div class="settings-row"><span>Density</span>${seg('density',[['comfortable','Comfortable'],['compact','Compact']])}</div>
  <div class="settings-row"><span>Reduce transparency</span>${seg('reduceTransparency',[['false','Off'],['true','On']])}</div></div>
  <div class="card" style="margin-top:14px"><h2>Data</h2>
  <div class="settings-row"><span>Refresh interval</span>${seg('refreshMs',[['1000','1 s'],['2000','2 s'],['5000','5 s']])}</div>
  <div class="settings-row"><span>Throughput alert (Mbit/s per app, 0 = off)</span><input id="alertInput" type="number" min="0" max="100000" value="${p.alertMbps}" aria-label="Throughput alert threshold in megabits per second"></div>
  <div class="settings-row"><span>Pinned applications</span><span class="muted">${p.pinned.map(esc).join(', ')||'none'}</span></div>
  <div class="settings-row"><span>Preferences are stored only in this browser. The API token is never stored.</span><button id="resetPrefs" class="glass-btn">Reset preferences</button></div></div>`;
}
function renderBody(s){
  const viewFns={overview,health,map:networkMap,applications,flows,domains,dns,interfaces,routes,vpn,local:localNetwork,fluxvm,security,timeline,investigator,settings};
  return (viewFns[state.view]||overview)(s);
}
function render(opts={}){
  const body=$('#contentBody'),s=state.snapshot;
  if(!s){
    body.innerHTML=state.error?`<div class="error-state"><strong>Can’t reach the Nivora collector</strong><p>${esc(state.error)}</p><button id="retryBtn" class="primary">Retry</button></div>`:'<div class="grid stats"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>';
    const r=$('#retryBtn');if(r)r.onclick=()=>refresh();
    return;
  }
  if(opts.tick){
    const ae=document.activeElement;
    if(ae&&body.contains(ae)&&/^(INPUT|SELECT|TEXTAREA)$/.test(ae.tagName))return;
    if(['timeline','investigator','settings'].includes(state.view))return;
  }
  body.innerHTML=renderBody(s);
  if(state.view==='timeline')loadTimeline();if(state.view==='health')loadSeries();if(state.view==='investigator')bindInvestigator();if(state.view==='security')bindSecurity();if(state.view==='overview')loadOverviewChart();
  if(state.sheetApp)renderSheet();
}

function drawOverviewChart(rows){
  const el=$('#overviewChart');if(!el)return;
  if(rows.length<2){el.innerHTML='<div class="empty">History will appear after a few samples.</div>';return}
  const W=800,H=150,max=Math.max(1,...rows.map(r=>Math.max(r.rx_bps||0,r.tx_bps||0)));
  const pts=k=>rows.map((r,i)=>`${(i/(rows.length-1)*W).toFixed(1)},${(H-4-((r[k]||0)/max)*(H-10)).toFixed(1)}`);
  const area=k=>`M0,${H} L${pts(k).join(' L')} L${W},${H} Z`;
  el.innerHTML=`<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Download and upload throughput history"><path class="rx" d="${area('rx_bps')}"/><path class="tx" d="${area('tx_bps')}"/></svg><div class="chart-tip"></div><div class="muted" style="font-size:11px;margin-top:6px">↓ blue · ↑ purple · peak ${fmtRate(max)}</div>`;
  const svg=el.querySelector('svg'),tip=el.querySelector('.chart-tip');
  svg.onmousemove=e=>{const r=svg.getBoundingClientRect(),i=Math.round((e.clientX-r.left)/r.width*(rows.length-1)),row=rows[Math.max(0,Math.min(rows.length-1,i))];
    tip.style.display='block';tip.style.left=`${Math.min(e.clientX-r.left+10,r.width-170)}px`;tip.style.top='8px';
    tip.textContent=`${new Date(row.timestamp).toLocaleTimeString()} · ↓ ${fmtRate(row.rx_bps||0)} · ↑ ${fmtRate(row.tx_bps||0)}`};
  svg.onmouseleave=()=>{tip.style.display='none'};
}
async function loadOverviewChart(){
  if(state.seriesCache)drawOverviewChart(state.seriesCache); // no skeleton flash between ticks
  try{
    const rows=await api('/v1/series?limit=80');state.seriesCache=rows;drawOverviewChart(rows);
  }catch(e){const el=$('#overviewChart');if(el&&!state.seriesCache)el.innerHTML=`<div class="empty">${esc(e.message||e)}</div>`}
}

/* app detail sheet */
function openSheet(name){state.sheetApp=name;renderSheet();$('#sheet').classList.add('open');$('#sheet').setAttribute('aria-hidden','false')}
function closeSheet(){state.sheetApp=null;$('#sheet').classList.remove('open');$('#sheet').setAttribute('aria-hidden','true')}
function renderSheet(){
  const s=state.snapshot,name=state.sheetApp,el=$('#sheet');if(!s||!name)return;
  const a=(s.apps||[]).find(x=>x.name===name),fl=(s.flows||[]).filter(f=>f.process===name);
  if(!a){el.innerHTML=`<div class="sheet-head"><h2>${esc(name)}</h2><button class="icon-btn close" id="sheetClose" aria-label="Close">✕</button></div><div class="empty">No current network activity for this application.</div>`;$('#sheetClose').onclick=closeSheet;return}
  const dests=[...new Set(fl.map(f=>hostOf(f.remote)))].slice(0,12),ports=[...new Set(fl.map(f=>portOf(f.remote)).filter(Boolean))].slice(0,12);
  el.innerHTML=`<div class="sheet-head"><div class="app-icon">${esc(initials(a.name))}</div><div><h2>${esc(a.name)}</h2><small class="muted">${a.pid?`PID ${a.pid} · `:''}${a.connections} connections</small></div><button class="icon-btn close" id="sheetClose" aria-label="Close">✕</button></div>
  <div class="sheet-stats"><div><span>↓ Live</span><b>${fmtRate(a.rx_bps||0)}</b></div><div><span>↑ Live</span><b>${fmtRate(a.tx_bps||0)}</b></div><div><span>Total</span><b>${fmtBytes((a.bytes_in||0)+(a.bytes_out||0))}</b></div></div>
  <svg viewBox="0 0 120 32" preserveAspectRatio="none" style="width:100%;height:48px" aria-hidden="true" class="talker"><path d="${sparklinePath(state.samples[name],120,32)}" style="fill:none;stroke:var(--blue);stroke-width:1.6"/></svg>
  <h3 style="margin:14px 0 6px">Destinations</h3><div>${dests.map(d=>badge(d)).join(' ')||'<span class="muted">none</span>'}</div>
  <h3 style="margin:14px 0 6px">Ports</h3><div>${ports.map(d=>badge(d)).join(' ')||'<span class="muted">none</span>'}</div>
  <h3 style="margin:14px 0 6px">Flows</h3>${flowTable(fl,false)}
  <h3 style="margin:14px 0 6px">Rules</h3><p class="muted" style="font-size:11px">Observe-first: blocking is leased for one hour and needs a signed NetworkExtension to take effect.</p>
  <div style="display:flex;gap:8px"><button class="glass-btn" data-rule="observe">Observe</button><button class="glass-btn" data-rule="allow">Allow</button><button class="glass-btn" data-rule="block">Block for 1 h</button></div>`;
  $('#sheetClose').onclick=closeSheet;
  el.querySelectorAll('[data-rule]').forEach(b=>b.onclick=async()=>{try{await api('/v1/rules',{method:'POST',body:JSON.stringify({action:b.dataset.rule,app:name})});toast(`Rule added: ${b.dataset.rule} ${name}`,'ok');refresh()}catch(e){toast(String(e.message||e),'error')}});
}

/* command palette */
let paletteIdx=0,paletteItems=[];
function buildPalette(q){
  q=q.trim().toLowerCase();const items=[];
  for(const [id,[sec,title]] of Object.entries(titles))items.push({label:title,hint:sec,run:()=>setView(id)});
  for(const v of state.prefs.views||[])items.push({label:v.name,hint:'Saved view',run:()=>{state.search=v.query;$('#search').value=v.query;setView('flows')}});
  for(const a of state.snapshot?.apps||[])items.push({label:a.name,hint:'Application',run:()=>openSheet(a.name)});
  const out=items.filter(i=>!q||i.label.toLowerCase().includes(q)).slice(0,10);
  if(q)out.push({label:`Ask Investigator: ${q}`,hint:'AI',run:()=>{setView('investigator');setTimeout(()=>{$('#question').value=q;$('#askBtn').click()},0)}});
  return out;
}
function drawPalette(){
  paletteItems=buildPalette($('#paletteInput').value);paletteIdx=Math.min(paletteIdx,Math.max(0,paletteItems.length-1));
  $('#paletteList').innerHTML=paletteItems.map((it,i)=>`<div class="palette-item" role="option" data-i="${i}" aria-selected="${i===paletteIdx}">${esc(it.label)}<small>${esc(it.hint)}</small></div>`).join('')||'<div class="empty">No matches</div>';
}
function openPalette(){const d=$('#paletteDialog');if(!d.open)d.showModal();$('#paletteInput').value='';paletteIdx=0;drawPalette();$('#paletteInput').focus()}
function runPalette(i){const it=paletteItems[i];if(!it)return;$('#paletteDialog').close();it.run()}

/* export */
function download(name,type,text){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function exportSnapshot(){if(!state.snapshot)return toast('Nothing to export yet','warn');download(`nivora-snapshot-${Date.now()}.json`,'application/json',JSON.stringify(state.snapshot,null,2));toast('Snapshot exported','ok')}
function exportFlows(){if(!state.snapshot)return toast('Nothing to export yet','warn');download(`nivora-flows-${Date.now()}.csv`,'text/csv',flowsToCSV(filteredFlows()));toast('Flows exported','ok')}

async function loadTimeline(){try{const events=await api('/v1/timeline');$('#timelineBody').innerHTML=events.slice().reverse().map(e=>`<div class="event"><time>${esc(new Date(e.ts).toLocaleString())} · ${esc(e.kind)}</time><strong>${esc(e.title)}</strong><p>${esc(e.detail||'')}</p></div>`).join('')||'<div class="empty">No changes recorded yet.</div>'}catch(e){$('#timelineBody').innerHTML=`<div class="empty">${esc(e)}</div>`}}
async function loadSeries(){try{const rows=await api('/v1/series?limit=80');const el=$('#seriesBody');if(!el)return;const max=Math.max(1,...rows.map(x=>(x.rx_bps||0)+(x.tx_bps||0)));el.innerHTML=rows.map(x=>`<div class="spark-col" title="${esc(new Date(x.timestamp).toLocaleTimeString())} · ↓ ${esc(fmtRate(x.rx_bps))} · ↑ ${esc(fmtRate(x.tx_bps))}"><i style="height:${Math.max(3,((x.rx_bps||0)+(x.tx_bps||0))/max*100)}%"></i></div>`).join('')||'<div class="empty">History will appear after a few samples.</div>'}catch(e){const el=$('#seriesBody');if(el)el.innerHTML=`<div class="empty">${esc(e)}</div>`}}
function bindInvestigator(){const ask=async()=>{const q=$('#question').value.trim();if(!q)return;$('#answer').innerHTML='<strong>Investigating…</strong>';try{const r=await api('/v1/query',{method:'POST',body:JSON.stringify({question:q})});$('#answer').innerHTML=`<strong>${esc(r.answer)}</strong>${(r.evidence||[]).length?`<pre class="mono" style="white-space:pre-wrap;max-height:260px;overflow:auto">${esc(JSON.stringify(r.evidence.slice(0,8),null,2))}</pre>`:'<span class="muted">No additional evidence.</span>'}`}catch(e){$('#answer').textContent=String(e)}};$('#askBtn').onclick=ask;$('#question').onkeydown=e=>{if(e.key==='Enter')ask()}}

$('#nav').onclick=e=>{const b=e.target.closest('button[data-view]');if(b)setView(b.dataset.view)};
$('#refreshBtn').onclick=()=>refresh();
function togglePause(){state.paused=!state.paused;const b=$('#pauseBtn');b.textContent=state.paused?'▶':'Ⅱ';b.setAttribute('aria-pressed',String(state.paused));b.setAttribute('aria-label',state.paused?'Resume updates':'Pause updates');setLive(!state.paused,state.paused?'Paused':null)}
$('#pauseBtn').onclick=togglePause;
$('#sidebarBtn').onclick=()=>document.documentElement.classList.toggle('sidebar-hidden');
$('#exportBtn').onclick=exportSnapshot;$('#exportCsvBtn').onclick=exportFlows;
$('#paletteBtn').onclick=openPalette;
$('#search').oninput=e=>{state.search=e.target.value;render()};
$('#themeBtn').onclick=()=>{const order=['auto','light','dark'];state.prefs.appearance=order[(order.indexOf(state.prefs.appearance)+1)%3];savePrefs();toast(`Appearance: ${state.prefs.appearance}`);if(state.view==='settings')render()};
$('#connectBtn').onclick=()=>{state.token=$('#tokenInput').value.trim();setTimeout(refresh,0)};

$('#paletteInput').oninput=()=>{paletteIdx=0;drawPalette()};
$('#paletteInput').onkeydown=e=>{
  if(e.key==='ArrowDown'){paletteIdx=Math.min(paletteItems.length-1,paletteIdx+1);drawPalette();e.preventDefault()}
  else if(e.key==='ArrowUp'){paletteIdx=Math.max(0,paletteIdx-1);drawPalette();e.preventDefault()}
  else if(e.key==='Enter')runPalette(paletteIdx);
};
$('#paletteList').onclick=e=>{const i=e.target.closest('[data-i]');if(i)runPalette(Number(i.dataset.i))};
for(const d of ['#paletteDialog','#helpDialog'])$(d).addEventListener('click',e=>{if(e.target===$(d))$(d).close()});

$('#contentBody').addEventListener('click',e=>{
  const sortTh=e.target.closest('th[data-sort]');
  if(sortTh){const so=state.sort[sortTh.dataset.view];so.dir=so.key===sortTh.dataset.sort&&so.dir==='desc'?'asc':'desc';so.key=sortTh.dataset.sort;render();return}
  const chip=e.target.closest('[data-chip]');
  if(chip){state.search=dropFilterChip(state.search,Number(chip.dataset.chip));$('#search').value=state.search;render();return}
  const vq=e.target.closest('[data-view-q]');
  if(vq){const v=state.prefs.views[Number(vq.dataset.viewQ)];if(v){state.search=v.query;$('#search').value=v.query;render()}return}
  const vd=e.target.closest('[data-view-del]');
  if(vd){state.prefs.views.splice(Number(vd.dataset.viewDel),1);savePrefs();render();return}
  if(e.target.closest('#saveViewBtn')){const q=state.search.trim(),name=q.length>28?q.slice(0,27)+'…':q;if(name&&!state.prefs.views.some(v=>v.query===q)){state.prefs.views.push({name,query:q});state.prefs.views=state.prefs.views.slice(-20);savePrefs();toast(`Saved view “${name}”`);render()}return}
  const pin=e.target.closest('[data-pin]');
  if(pin){const n=pin.dataset.pin,p=state.prefs.pinned;state.prefs.pinned=p.includes(n)?p.filter(x=>x!==n):[...p,n];savePrefs();render();e.stopPropagation();return}
  const pref=e.target.closest('[data-pref]');
  if(pref){const k=pref.dataset.pref;let v=pref.dataset.value;if(k==='refreshMs')v=Number(v);if(k==='reduceTransparency')v=v==='true';state.prefs=mergePrefs({...state.prefs,[k]:v});savePrefs();render();return}
  if(e.target.closest('#resetPrefs')){state.prefs=mergePrefs(null);savePrefs();render();toast('Preferences reset','ok');return}
  const row=e.target.closest('[data-app]');if(row)openSheet(row.dataset.app);
});
$('#contentBody').addEventListener('keydown',e=>{if(e.key==='Enter'){const t=e.target.closest('th[data-sort]');if(t)t.click()}});
$('#contentBody').addEventListener('change',e=>{if(e.target.id==='alertInput'){state.prefs=mergePrefs({...state.prefs,alertMbps:Number(e.target.value)});savePrefs();state.alerted.clear();toast(state.prefs.alertMbps?`Alert at ${state.prefs.alertMbps} Mbit/s per app`:'Alerts off','ok')}});

const gKeys={o:'overview',h:'health',m:'map',a:'applications',f:'flows'};
document.addEventListener('keydown',e=>{
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openPalette();return}
  if(e.key==='Escape'&&state.sheetApp){closeSheet();return}
  if(e.metaKey||e.ctrlKey||e.altKey||/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)||document.querySelector('dialog[open]'))return;
  if(state.goto){state.goto=false;if(gKeys[e.key])setView(gKeys[e.key]);return}
  if(e.key==='/'){e.preventDefault();$('#search').focus()}
  else if(e.key==='p')togglePause();
  else if(e.key==='r')refresh();
  else if(e.key==='g'){state.goto=true;setTimeout(()=>{state.goto=false},1200)}
  else if(e.key==='?')$('#helpDialog').showModal();
});

applyPrefs();parseToken();render();refresh();
