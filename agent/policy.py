# SPDX-License-Identifier: BUSL-1.1
"""Policy-as-code: a JSON file of desired rules, planned against the live rule store before applying.

{"name": "work-laptop", "rules": [{"action": "shadow", "domain": "example.com"}, ...]}
Blocks are leased exactly like rules added by hand unless a rule says `"permanent": true`.
"""
from __future__ import annotations

from typing import Any

from nivora_core import RuleStore

KEYS = ("action", "app", "domain", "ip", "port")


def _key(rule: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(rule.get(k) for k in KEYS)


def _marker(name: str) -> str:
    return f"policy:{name}"


def validate_policy(policy: Any) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(policy, dict):
        raise ValueError("policy must be an object")
    name = str(policy.get("name") or "").strip()
    if not name or len(name) > 64 or not all(c.isalnum() or c in "-_." for c in name):
        raise ValueError("policy needs a name (letters, digits, - _ .)")
    rules = policy.get("rules")
    if not isinstance(rules, list) or len(rules) > 500:
        raise ValueError("rules must be a list of at most 500")
    cleaned = []
    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            raise ValueError(f"rule {i + 1} must be an object")
        try:
            c = RuleStore.clean_rule(r)
        except ValueError as exc:
            raise ValueError(f"rule {i + 1}: {exc}") from exc
        c["note"] = _marker(name)
        cleaned.append(c)
    keys = [_key(c) for c in cleaned]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate rules in policy")
    return name, cleaned


def plan_policy(store: RuleStore, policy: Any) -> dict[str, Any]:
    name, desired = validate_policy(policy)
    existing = [r for r in store.list() if r.get("note") == _marker(name) and r.get("active", True)]
    have = {_key(r): r for r in existing}
    want = {_key(r): r for r in desired}
    return {
        "name": name,
        "add": [want[k] for k in want if k not in have],
        "remove": [have[k] for k in have if k not in want],
        "unchanged": [have[k] for k in have if k in want],
    }


def apply_policy(store: RuleStore, policy: Any) -> dict[str, Any]:
    plan = plan_policy(store, policy)
    for r in plan["remove"]:
        store.remove(r["id"])
    added = []
    for r in plan["add"]:
        raw = {k: v for k, v in r.items() if k in {"app", "domain", "ip", "port", "action", "note", "expires_at"}}
        if r.get("action") == "block" and not r.get("lease_seconds") and not r.get("expires_at"):
            raw["permanent"] = True
        elif r.get("lease_seconds"):
            raw["duration_seconds"] = r["lease_seconds"]
            raw.pop("expires_at", None)
        added.append(store.add(raw))
    return {"name": plan["name"], "added": added, "removed": plan["remove"], "unchanged": plan["unchanged"]}


def export_policy(store: RuleStore, name: str) -> dict[str, Any]:
    rules = []
    for r in store.list():
        if not r.get("active", True):
            continue
        item = {k: r[k] for k in KEYS if r.get(k) not in (None, "")}
        if item.get("action") == "block" and not r.get("expires_at"):
            item["permanent"] = True
        rules.append(item)
    return {"name": name, "rules": rules}
