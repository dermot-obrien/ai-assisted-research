#!/usr/bin/env python3
# Copyright 2026 Dermot O'Brien -- GPLv3
"""
Generate node-index.yaml from the hypothesis DAG.

Computes parent-resolved readiness for each node and classifies them as:
  - ready: pending nodes whose parent is completed, validated, or ineffective
  - active: nodes with status in_progress, partially_tested, or contested
  - framed: nodes with status framed
  - blocked: pending nodes whose parent is still pending, in_progress, etc.

Usage:
    python .ai-assisted-research/tools/generate_node_index.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DAG_PATH = REPO_ROOT / ".irregular-timeseries-intent" / "change" / "work-items" / \
    "WI-032-irregular-timeseries-analysis" / "deliverables" / "D01-hypothesis-dag.yaml"
OUTPUT_PATH = REPO_ROOT / "node-index.yaml"

RESOLVED_STATUSES = {"completed", "validated", "ineffective"}
ACTIVE_STATUSES = {"in_progress", "partially_tested", "contested"}


def main():
    with open(DAG_PATH, encoding="utf-8") as f:
        dag = yaml.safe_load(f)

    nodes = dag.get("nodes", [])
    node_map = {n["id"]: n for n in nodes}

    ready = []
    active = []
    framed = []
    blocked = []

    for n in nodes:
        status = n.get("status", "pending")
        nid = n["id"]
        parent_id = n.get("parent")

        if status in RESOLVED_STATUSES:
            continue  # Already resolved, not actionable

        if status in ACTIVE_STATUSES:
            active.append({
                "id": nid,
                "parent": parent_id,
                "status": status,
                "hypothesis": n.get("hypothesis", "")[:120],
            })
            continue

        if status == "framed":
            framed.append({
                "id": nid,
                "parent": parent_id,
                "hypothesis": n.get("hypothesis", "")[:120],
            })
            continue

        # Status is pending — check if parent is resolved
        if parent_id is None:
            # Root node
            ready.append({
                "id": nid,
                "parent": parent_id,
                "hypothesis": n.get("hypothesis", "")[:120],
            })
            continue

        parent = node_map.get(parent_id)
        if parent and parent.get("status") in RESOLVED_STATUSES:
            ready.append({
                "id": nid,
                "parent": parent_id,
                "hypothesis": n.get("hypothesis", "")[:120],
            })
        else:
            # Find blocker chain
            blockers = []
            current = parent_id
            while current:
                p = node_map.get(current)
                if not p:
                    break
                if p.get("status") not in RESOLVED_STATUSES:
                    blockers.append(current)
                current = p.get("parent")

            entry = {
                "id": nid,
                "parent": parent_id,
                "hypothesis": n.get("hypothesis", "")[:120],
            }
            if blockers:
                entry["blocked_by"] = blockers
            blocked.append(entry)

    index = {
        "source_dag": "hypothesis-dag.yaml",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_nodes": len(nodes),
        "ready": ready,
        "active": active,
    }
    if framed:
        index["framed"] = framed
    if blocked:
        index["blocked"] = blocked

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("# Node Index\n\n")
        yaml.dump(index, f, sort_keys=False, default_flow_style=False, allow_unicode=True)

    print(f"Node index generated: {OUTPUT_PATH}")
    print(f"  Total nodes: {len(nodes)}")
    print(f"  Ready: {len(ready)}")
    print(f"  Active: {len(active)}")
    print(f"  Framed: {len(framed)}")
    print(f"  Blocked: {len(blocked)}")


if __name__ == "__main__":
    main()
