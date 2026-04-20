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

from datetime import datetime, timezone

import yaml

import rms_config

RESOLVED_STATUSES = {"completed", "validated", "ineffective"}
ACTIVE_STATUSES = {"in_progress", "partially_tested", "contested"}


def main():
    cfg = rms_config.load()
    dag_path = cfg.dag_path
    output_path = cfg.node_index_path

    with open(dag_path, encoding="utf-8") as f:
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
        "source_dag": str(dag_path.relative_to(cfg.repo_root)),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_nodes": len(nodes),
        "ready": ready,
        "active": active,
    }
    if framed:
        index["framed"] = framed
    if blocked:
        index["blocked"] = blocked

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Node Index\n\n")
        yaml.dump(index, f, sort_keys=False, default_flow_style=False, allow_unicode=True)

    print(f"Node index generated: {output_path}")
    print(f"  Total nodes: {len(nodes)}")
    print(f"  Ready: {len(ready)}")
    print(f"  Active: {len(active)}")
    print(f"  Framed: {len(framed)}")
    print(f"  Blocked: {len(blocked)}")


if __name__ == "__main__":
    main()
