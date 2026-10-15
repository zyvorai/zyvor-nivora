#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
from __future__ import annotations
import argparse, json, os, subprocess, urllib.error, urllib.parse, urllib.request

DEFAULT = os.getenv("NIVORA_URL", "http://127.0.0.1:9857")

def keychain_token():
    if os.getenv("NIVORA_TOKEN"): return os.environ["NIVORA_TOKEN"]
    try:
        p=subprocess.run(["security","find-generic-password","-s","dev.zyvor.nivora","-a",os.getenv("USER", ""),"-w"],capture_output=True,text=True,timeout=1)
        if p.returncode==0: return p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired): pass
    return ""

def request(base,path,token,method="GET",body=None):
    headers={"Accept":"application/json"}
    if token: headers["Authorization"]="Bearer "+token
    data=None
    if body is not None:
        data=json.dumps(body).encode(); headers["Content-Type"]="application/json"
    req=urllib.request.Request(base.rstrip('/')+path,data=data,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=3) as r: return json.loads(r.read())

def table(rows, fields):
    rows=list(rows)
    widths={k:max(len(label),*(len(str(r.get(k,""))) for r in rows)) for k,label in fields}
    print("  ".join(label.ljust(widths[k]) for k,label in fields))
    print("  ".join("-"*widths[k] for k,_ in fields))
    for r in rows: print("  ".join(str(r.get(k,"")).ljust(widths[k]) for k,_ in fields))

def main():
    p=argparse.ArgumentParser(prog="nivoractl",description="Nivora local CLI")
    p.add_argument("--url",default=DEFAULT);p.add_argument("--token",default=keychain_token())
    sub=p.add_subparsers(dest="cmd",required=True)
    for c in ["status","apps","interfaces","routes","dns","vpn","fluxvm","findings","timeline","rules","health","traffic","topology","neighbors","listeners","behavior","diagnose","series"]: sub.add_parser(c)
    sub.add_parser("flows").add_argument("--filter", default="", help='e.g. app:Safari port:443 proto:tcp >1mbps')
    a=sub.add_parser("ask");a.add_argument("question",nargs="+")
    a=sub.add_parser("rule-add");a.add_argument("--action",choices=["observe","allow","block","shadow"],default="observe");a.add_argument("--app");a.add_argument("--domain");a.add_argument("--ip");a.add_argument("--port",type=int);a.add_argument("--expires-at");a.add_argument("--duration",type=int,help="block lease seconds (default 3600)");a.add_argument("--permanent",action="store_true")
    a=sub.add_parser("explain");a.add_argument("flow_id")
    sub.add_parser("rule-impact")
    a=sub.add_parser("rule-delete");a.add_argument("id")
    args=p.parse_args()
    try:
        if args.cmd=="status":
            s=request(args.url,"/v1/snapshot",args.token); print(json.dumps({"host":s["host"],"capabilities":s["capabilities"],"apps":len(s["apps"]),"flows":len(s["flows"]),"findings":len(s["findings"])},indent=2)); return
        if args.cmd=="apps":
            rows=request(args.url,"/v1/apps",args.token); table(rows,[("name","APP"),("connections","CONN"),("bytes_in","RX"),("bytes_out","TX")]); return
        if args.cmd=="flows":
            rows=request(args.url,"/v1/flows"+("?"+urllib.parse.urlencode({"filter":args.filter}) if args.filter else ""),args.token); table(rows,[("process","APP"),("protocol","PROTO"),("remote","REMOTE"),("interface","IFACE"),("state","STATE")]); return
        path={"interfaces":"/v1/interfaces","routes":"/v1/routes","dns":"/v1/dns","vpn":"/v1/vpn","fluxvm":"/v1/fluxvm","findings":"/v1/findings","timeline":"/v1/timeline","rules":"/v1/rules","health":"/v1/health","traffic":"/v1/traffic","topology":"/v1/topology","neighbors":"/v1/neighbors","listeners":"/v1/listeners","behavior":"/v1/behavior","diagnose":"/v1/diagnose","series":"/v1/series"}.get(args.cmd)
        if path: print(json.dumps(request(args.url,path,args.token),indent=2)); return
        if args.cmd=="explain": print(json.dumps(request(args.url,"/v1/flows/"+urllib.parse.quote(args.flow_id,safe="")+"/explain",args.token),indent=2)); return
        if args.cmd=="rule-impact": print(json.dumps(request(args.url,"/v1/rule-impact",args.token),indent=2)); return
        if args.cmd=="ask": print(json.dumps(request(args.url,"/v1/query",args.token,"POST",{"question":" ".join(args.question)}),indent=2)); return
        if args.cmd=="rule-add":
            body={k:getattr(args,k) for k in ["action","app","domain","ip","port","expires_at"] if getattr(args,k,None) is not None}; body.update({"duration_seconds":args.duration} if args.duration else {}); body.update({"permanent":True} if args.permanent else {})
            print(json.dumps(request(args.url,"/v1/rules",args.token,"POST",body),indent=2)); return
        if args.cmd=="rule-delete": print(json.dumps(request(args.url,"/v1/rules/"+args.id,args.token,"DELETE"),indent=2)); return
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Nivora API: HTTP {e.code}: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e: raise SystemExit(f"Nivora API unavailable: {e.reason}")

if __name__=="__main__": main()
