#!/usr/bin/env python3
# Copyright 2026 Dermot O'Brien -- GPLv3
"""
Validate that all hypothesis IDs referenced in code, docs, and experiment logs
exist in the hypothesis DAG (D01-hypothesis-dag.yaml).

Catches the case where an agent creates hypothesis IDs in code/docs/experiments
without registering them in the central DAG.

Usage:
    python .ai-assisted-research/tools/validate_dag_references.py
    python .ai-assisted-research/tools/validate_dag_references.py --fix  # show what to add

Exit code:
    0 = all references valid
    1 = orphaned references found
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DAG_PATH = REPO_ROOT / ".irregular-timeseries-intent" / "change" / "work-items" / \
    "WI-032-irregular-timeseries-analysis" / "deliverables" / "D01-hypothesis-dag.yaml"
EXPERIMENTS_DIR = REPO_ROOT / "autoresearch" / "experiments"

# Directories to scan for hypothesis ID references
SCAN_DIRS = [
    REPO_ROOT / "autoresearch",
    REPO_ROOT / "docs",
    REPO_ROOT / ".irregular-timeseries-intent",
    REPO_ROOT / "python",
]

# File extensions to scan
SCAN_EXTENSIONS = {".py", ".md", ".yaml", ".yml", ".jsonl", ".json"}

# Pattern to match hypothesis IDs like H-204.4.7, H-100, H-204.3.9.10
# Requires at least 2 digits after H- to avoid matching math like {0,...,H-1}
HYPOTHESIS_PATTERN = re.compile(r"\bH-\d{2,}(?:\.\d+)*[a-z]?\b")

# Legacy hypothesis IDs that predate the current DAG numbering scheme.
# These are referenced in older docs/work-items but were never migrated to the
# H-xxx structured DAG. They are not errors — just historical references.
LEGACY_IDS = {
    "H-4.5b",     # WI-035: GNN bottom-up aggregation (→ now covered by H-500 branch)
    "H-4.5c",     # WI-035: Multi-horizon forecasting (→ now covered by H-500 branch)
    "H-1.6",      # WI-035: Tick embedding geometry (→ now H-413 in the DAG)
    "H-204.3.5b", # Informal variant label (conf 0.70 variant of H-204.3.5)
    "H-504.1",    # Proposed in D08 (directed GNN for forecasting, low priority, not yet added to DAG)
    "H-705",      # Proposed in WI-034 D02 (tick-level microstructure, pending)
    "H-706",      # Proposed in WI-034 D02 (temporal point processes, pending)
}


def load_dag_ids() -> set[str]:
    """Load all hypothesis IDs from the DAG YAML."""
    try:
        import yaml
    except ImportError:
        # Fallback: parse IDs with regex from raw file
        text = DAG_PATH.read_text(encoding="utf-8")
        return set(re.findall(r"^\s+- id: (H-\S+)", text, re.MULTILINE))

    with open(DAG_PATH, encoding="utf-8") as f:
        dag = yaml.safe_load(f)

    ids = set()
    for node in dag.get("nodes", []):
        ids.add(node["id"])
    return ids


def scan_file(path: Path) -> dict[str, list[int]]:
    """Scan a file for hypothesis ID references. Returns {id: [line_numbers]}."""
    refs: dict[str, list[int]] = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for lineno, line in enumerate(f, 1):
                for match in HYPOTHESIS_PATTERN.finditer(line):
                    hid = match.group()
                    refs.setdefault(hid, []).append(lineno)
    except (OSError, UnicodeDecodeError):
        pass
    return refs


def main():
    fix_mode = "--fix" in sys.argv

    dag_ids = load_dag_ids()
    print(f"DAG contains {len(dag_ids)} hypothesis IDs")

    # Scan all relevant files
    all_refs: dict[str, list[tuple[str, list[int]]]] = {}  # {id: [(file, [lines])]}

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for path in scan_dir.rglob("*"):
            if path.suffix not in SCAN_EXTENSIONS:
                continue
            if path.name == "validate_dag_references.py":
                continue
            refs = scan_file(path)
            for hid, lines in refs.items():
                all_refs.setdefault(hid, []).append(
                    (str(path.relative_to(REPO_ROOT)), lines)
                )

    # Find orphaned IDs (referenced but not in DAG, excluding legacy)
    referenced_ids = set(all_refs.keys())
    orphaned = referenced_ids - dag_ids - LEGACY_IDS

    # Filter out IDs that appear only in the DAG file itself
    orphaned_with_refs = {}
    for hid in sorted(orphaned):
        external_refs = [
            (f, lines) for f, lines in all_refs[hid]
            if "D01-hypothesis-dag" not in f
        ]
        if external_refs:
            orphaned_with_refs[hid] = external_refs

    if not orphaned_with_refs:
        print("All hypothesis ID references are registered in the DAG.")
        return 0

    print(f"\nFOUND {len(orphaned_with_refs)} ORPHANED HYPOTHESIS IDs:")
    print("These IDs are referenced in code/docs/experiments but missing from the DAG.\n")

    for hid in sorted(orphaned_with_refs.keys()):
        refs = orphaned_with_refs[hid]
        print(f"  {hid}")
        for filepath, lines in refs:
            line_str = ", ".join(str(ln) for ln in lines[:5])
            if len(lines) > 5:
                line_str += f", ... ({len(lines)} total)"
            print(f"    {filepath}:{line_str}")

    if fix_mode:
        print("\nTo fix, add these nodes to D01-hypothesis-dag.yaml:")
        print("(You must fill in parent, hypothesis, and other fields)\n")
        for hid in sorted(orphaned_with_refs.keys()):
            print(f"""  - id: {hid}
    parent: ???           # FILL IN
    hypothesis: "???"     # FILL IN
    status: pending
    work_item_id: null
    target_improvement: null
    actual_performance: null
    evidence: null
""")

    return 1


if __name__ == "__main__":
    sys.exit(main())
