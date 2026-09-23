# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""
Reconcile the hypothesis DAG against the running system.

A hypothesis has two independent states: whether it is true (`status`) and
whether it is live (`adoption.state`). This tool checks the second. See
docs/adoption-and-drift.md.

It reports the gap and proposes nothing. A reconciliation that proposes fixes
invites arguing about the fixes instead of accepting the gap.

Usage:
    python tools/reconcile.py --dag research/hypothesis-dag.yaml
    python tools/reconcile.py --dag ... --migrate      # seed missing adoption blocks
    python tools/reconcile.py --dag ... --json         # machine-readable
    python tools/reconcile.py --dag ... --strict       # also fail on unverified claims

Exit codes:
    0  no drift
    1  drift found, or a claim that cannot be verified under --strict
    2  usage or file error
"""

import argparse
import datetime
import io
import re
import json
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is required: python -m pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)


ADOPTION_STATES = [
    "not_assessed",
    "not_applicable",
    "not_adopted",
    "partial",
    "adopted",
    "contradicted",
]

# States that assert something about the running system, so they owe a predicate.
CLAIMS_REALITY = {"adopted", "partial", "contradicted"}

DEFAULT_ADOPTION = {
    "state": "not_assessed",
    "artefact": None,
    "verification": None,
    "verified_on": None,
    "note": None,
}


def iter_nodes(dag):
    """Yield every hypothesis node, wherever it sits in the document."""
    seen = set()

    def walk(o):
        if isinstance(o, dict):
            nid = o.get("id")
            if isinstance(nid, str) and nid.startswith("H-") and "status" in o:
                if nid not in seen:
                    seen.add(nid)
                    yield o
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)

    yield from walk(dag)


def run_predicate(cmd, cwd, timeout):
    """Run an adoption predicate. Zero exit means the claim still holds."""
    try:
        r = subprocess.run(
            cmd, shell=True, cwd=cwd, timeout=timeout,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        return r.returncode == 0, (r.stdout or b"").decode("utf-8", "replace").strip()[:300]
    except subprocess.TimeoutExpired:
        return False, "predicate timed out after %ss" % timeout
    except Exception as e:  # noqa: BLE001 - a broken predicate is a finding, not a crash
        return False, "predicate failed to run: %s" % e


NODE_LINE = re.compile(r"^(\s*)-\s+id:\s*(H-[\w.]+)\s*$")


def migrate(path):
    """Add a default adoption block to every node that lacks one. Infers nothing.

    This edits the file textually rather than round-tripping through the YAML
    parser. A DAG is a research record: its comments carry the status key, the
    conventions and the standing findings, and safe_dump would silently drop all
    of them and reflow every block scalar. The diff must show the blocks being
    added and nothing else.
    """
    # newline="" so the file's own line endings survive verbatim. Without it
    # Python's universal-newline translation rewrites CRLF to LF and the diff
    # covers every line in the file instead of just the added blocks.
    raw = io.open(path, encoding="utf-8", newline="").read()
    dag = yaml.safe_load(raw)

    # Which node ids already have a block, decided by the parser rather than by
    # guessing from the text.
    have = {n["id"] for n in iter_nodes(dag) if isinstance(n.get("adoption"), dict)}

    lines = raw.splitlines(keepends=True)
    out = []
    touched = 0

    for line in lines:
        out.append(line)
        m = NODE_LINE.match(line.rstrip("\n").rstrip("\r"))
        if not m:
            continue
        indent, nid = m.group(1), m.group(2)
        if nid in have:
            continue
        # Keys sit two columns right of the dash that opens the list item.
        k = indent + "  "
        nl = "\r\n" if line.endswith("\r\n") else "\n"
        for extra in (
            "adoption:",
            "  state: not_assessed",
            "  artefact: null",
            "  verification: null",
            "  verified_on: null",
            "  note: null",
        ):
            out.append(k + extra + nl)
        touched += 1

    if touched:
        io.open(path, "w", encoding="utf-8", newline="").write("".join(out))

        # The file must still parse, and must still hold the same nodes.
        after = yaml.safe_load(io.open(path, encoding="utf-8").read())
        before_ids = [n["id"] for n in iter_nodes(dag)]
        after_ids = [n["id"] for n in iter_nodes(after)]
        if before_ids != after_ids:
            raise SystemExit("migrate: node set changed; file left as written, inspect the diff")
        missing = [n["id"] for n in iter_nodes(after) if not isinstance(n.get("adoption"), dict)]
        if missing:
            raise SystemExit("migrate: %d node(s) still lack a block: %s" % (len(missing), missing[:5]))

    print("migrate: %d node(s) given a default adoption block" % touched)
    print("         all at state 'not_assessed' — nothing was inferred")
    print("         comments and formatting preserved; re-parsed and node set verified")
    return 0


def reconcile(path, cwd, timeout, strict, as_json):
    dag = yaml.safe_load(open(path, encoding="utf-8"))
    nodes = list(iter_nodes(dag))

    findings = []
    counts = {s: 0 for s in ADOPTION_STATES}
    counts["missing_block"] = 0
    checked = passed = 0

    ids = {n["id"] for n in nodes}

    for node in nodes:
        nid = node["id"]
        ad = node.get("adoption")

        if not isinstance(ad, dict):
            counts["missing_block"] += 1
            findings.append({
                "node": nid, "kind": "no_adoption_block",
                "detail": "node has no adoption block; run --migrate",
            })
            continue

        state = ad.get("state", "not_assessed")
        counts[state] = counts.get(state, 0) + 1

        # A blocked_by pointing at an unknown node is a broken reference.
        for dep in node.get("blocked_by") or []:
            if dep not in ids:
                findings.append({
                    "node": nid, "kind": "unknown_blocker",
                    "detail": "blocked_by references unknown node %s" % dep,
                })

        for dep in node.get("contested_by") or []:
            if dep not in ids:
                findings.append({
                    "node": nid, "kind": "unknown_contester",
                    "detail": "contested_by references unknown node %s" % dep,
                })

        # A validated node that is absent with nothing blocking it is the gap
        # this tool exists to surface.
        if node.get("status") == "validated" and state == "not_adopted" and not (node.get("blocked_by") or []):
            findings.append({
                "node": nid, "kind": "validated_not_adopted",
                "detail": "validated, nothing in blocked_by, and not adopted",
            })

        if node.get("status") == "validated" and state == "contradicted":
            findings.append({
                "node": nid, "kind": "validated_contradicted",
                "detail": "the system does what this validated node warns against",
            })

        pred = ad.get("verification")

        if state in CLAIMS_REALITY and not pred:
            findings.append({
                "node": nid, "kind": "unverified_claim",
                "detail": "state '%s' asserts something about the running system "
                          "but carries no verification predicate" % state,
            })
            continue

        if not pred:
            continue

        checked += 1
        ok, out = run_predicate(pred, cwd, timeout)
        if ok:
            passed += 1
        else:
            findings.append({
                "node": nid, "kind": "drift",
                "detail": "adoption predicate no longer holds",
                "predicate": pred,
                "output": out,
            })

    report = {
        "dag": path,
        "generated": datetime.date.today().isoformat(),
        "nodes": len(nodes),
        "counts": counts,
        "predicates_run": checked,
        "predicates_passed": passed,
        "findings": findings,
    }

    if as_json:
        print(json.dumps(report, indent=2))
    else:
        emit(report)

    hard = [f for f in findings if f["kind"] != "unverified_claim"]
    if hard:
        return 1
    if strict and findings:
        return 1
    return 0


def emit(r):
    print("Reconciliation of %s" % r["dag"])
    print("%d node(s); %d predicate(s) run, %d passed" % (r["nodes"], r["predicates_run"], r["predicates_passed"]))
    print()
    print("Adoption states")
    for k in ADOPTION_STATES:
        n = r["counts"].get(k, 0)
        if n:
            print("  %-16s %d" % (k, n))
    if r["counts"].get("missing_block"):
        print("  %-16s %d" % ("(no block)", r["counts"]["missing_block"]))
    print()

    if not r["findings"]:
        print("No drift.")
        return

    order = ["drift", "validated_contradicted", "validated_not_adopted",
             "unverified_claim", "unknown_blocker", "unknown_contester", "no_adoption_block"]
    print("Findings: %d" % len(r["findings"]))
    for kind in order:
        group = [f for f in r["findings"] if f["kind"] == kind]
        if not group:
            continue
        print()
        print("  %s (%d)" % (kind, len(group)))
        for f in group:
            print("    %-14s %s" % (f["node"], f["detail"]))
            if f.get("predicate"):
                print("      $ %s" % f["predicate"])
            if f.get("output"):
                print("      %s" % f["output"])


def main():
    p = argparse.ArgumentParser(description="Reconcile the hypothesis DAG against the running system.")
    p.add_argument("--dag", default="research/hypothesis-dag.yaml", help="Path to hypothesis-dag.yaml")
    p.add_argument("--cwd", default=".", help="Working directory predicates run in")
    p.add_argument("--timeout", type=int, default=60, help="Per-predicate timeout in seconds")
    p.add_argument("--migrate", action="store_true", help="Seed missing adoption blocks, then exit")
    p.add_argument("--strict", action="store_true", help="Also fail when a claim carries no predicate")
    p.add_argument("--json", action="store_true", dest="as_json", help="Machine-readable output")
    a = p.parse_args()

    try:
        if a.migrate:
            sys.exit(migrate(a.dag))
        sys.exit(reconcile(a.dag, a.cwd, a.timeout, a.strict, a.as_json))
    except FileNotFoundError:
        print("DAG not found: %s" % a.dag, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
