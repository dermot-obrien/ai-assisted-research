#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""
The hypothesis pool: a pool of agents, in any tool, takes hypotheses from the board and runs them in
parallel, with the DAG deciding what may be offered and the board's claims keeping two agents off one
node. A held node keeps everything below it waiting, because a child is offered only once its parent's
work is settled.

Two kinds of work go on the board:

    research    a node that is pending or framed and whose parent is resolved: frame it, run it,
                sync it (/research progress for one node). Posted with --ref <node id>.
    campaign    a node with a result, in a campaign that retests the whole DAG from the root down:
                replay or rebuild it, and record a verdict. Posted with --ref <campaign>-<node id>,
                offered once every ancestor with a result has its verdict in the campaign.

    python pool.py offer [--campaign RT1] [--dry-run]     post every node that may start now
    python pool.py status [--campaign RT1]                what is offered, held, done, and waiting
    python pool.py check <node> [--campaign RT1]          whether an agent may work on (or under) a node
    python pool.py record <node> --campaign RT1 --verdict reproduced|rebuilt|differs|unverifiable
                          [--capsule ID] [--note TEXT] [--agent HANDLE]
    python pool.py revisit --campaign RT1                 the unverifiable nodes, the most depended on first
    python pool.py review [--campaign RT1] [--json] [--no-board]
                                                          one snapshot of every hypothesis, for a person or a view

It reads research.yaml (dag_path, and a pool: section) and runs the thread skill's CLI for the board:

    pool:
      thread: "node ../thread/skills/thread/bin/thread.mjs"   # how to run the thread CLI (or $THREAD_CMD)
      source: "research"                                       # the board path the pool works in
      on_thread: "t-4k2"                                       # the thread the calls hang under
      as: "pool-coordinator"                                   # the handle that posts (or $BOARD_AS)

A node with `runner: <name>` (for example `runner: local-gpu`) is posted to the role runner:<name>
instead of to any agent, so only the session holding that role (on the machine with the GPU) takes it.

Exit codes: 0 done (check: may work), 1 check: may not work, 2 usage or configuration error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required: python -m pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)

DAG_BIN = Path(os.environ.get("RESEARCH_DAG_BIN") or Path(__file__).resolve().parents[2] / "research-dag" / "bin")
sys.path.insert(0, str(DAG_BIN))

import rms_config  # noqa: E402

RESOLVED = {"completed", "validated", "ineffective", "holdout_passed", "forward_testing", "retired"}
STARTABLE = {"pending", "framed"}
# Nodes with a result a campaign retests: every status that records an outcome, the old ones too.
RESULT = {"validated", "ineffective", "contested", "backtested", "holdout_passed", "forward_testing", "retired",
          "completed", "tested", "partially_tested"}
VERDICTS = ("reproduced", "rebuilt", "differs", "unverifiable")


class PoolError(Exception):
    pass


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Pool:
    def __init__(self, cfg: rms_config.Config, campaign: str | None):
        self.cfg = cfg
        self.campaign = campaign
        pool = cfg._get("pool", None) or {}
        self.thread = shlex.split(os.environ.get("THREAD_CMD") or pool.get("thread") or "thread")
        self.source = pool.get("source")
        self.on = pool.get("on_thread")
        self.handle = os.environ.get("BOARD_AS") or pool.get("as")
        if cfg.uses_dag_store:
            subprocess.run([sys.executable, str(DAG_BIN / "dag_store.py"), "view"], cwd=cfg.repo_root,
                           capture_output=True, text=True)
        dag = yaml.safe_load(cfg.dag_path.read_text(encoding="utf-8")) or {}
        self.nodes = [n for n in dag.get("nodes", []) if isinstance(n, dict) and n.get("id")]
        self.by_id = {n["id"]: n for n in self.nodes}
        self.children: dict[str, list[str]] = {}
        for n in self.nodes:
            for p in self.parents(n):
                self.children.setdefault(p, []).append(n["id"])

    # ---- the DAG

    def parents(self, node: dict) -> list[str]:
        ps = node.get("parents") or ([node["parent"]] if node.get("parent") else [])
        return [p for p in ps if p in self.by_id]

    def ancestors(self, nid: str) -> list[str]:
        out, todo = [], list(self.parents(self.by_id[nid]))
        while todo:
            p = todo.pop()
            if p not in out:
                out.append(p)
                todo.extend(self.parents(self.by_id[p]))
        return out

    def descendants(self, nid: str) -> list[str]:
        out, todo = [], list(self.children.get(nid, []))
        while todo:
            c = todo.pop()
            if c not in out:
                out.append(c)
                todo.extend(self.children.get(c, []))
        return out

    def verdict(self, nid: str) -> dict | None:
        rows = [r for r in self.by_id[nid].get("retests") or []
                if isinstance(r, dict) and r.get("campaign") == self.campaign]
        return rows[-1] if rows else None

    def ref(self, nid: str) -> str:
        return f"{self.campaign}-{nid}" if self.campaign else nid

    def startable(self, nid: str) -> tuple[bool, str]:
        """Whether a node's work may start now, and if not, what it waits for."""
        n = self.by_id[nid]
        if self.campaign:
            if n.get("status") not in RESULT:
                return False, "has no result to retest"
            if self.verdict(nid):
                return False, "has its verdict"
            waiting = [a for a in self.ancestors(nid) if self.by_id[a].get("status") in RESULT and not self.verdict(a)]
            return (not waiting), (f"waits for {', '.join(sorted(waiting))}" if waiting else "")
        if n.get("status") not in STARTABLE:
            return False, f"is {n.get('status')}"
        waiting = [p for p in self.parents(n) if self.by_id[p].get("status") not in RESOLVED]
        return (not waiting), (f"waits for {', '.join(sorted(waiting))}" if waiting else "")

    # ---- the board

    def board(self, *args: str, check: bool = True) -> str:
        cmd = [*self.thread, "board", *args]
        p = subprocess.run(cmd, cwd=self.cfg.repo_root, capture_output=True, text=True)
        if check and p.returncode != 0:
            raise PoolError(f"{' '.join(cmd)} failed: {(p.stdout + p.stderr).strip()[:400]}")
        return p.stdout

    def board_state(self) -> dict[str, dict]:
        """For each ref of this pool: its latest call, whether it is done, and who holds it."""
        scope = ["--source", self.source] if self.source else []
        posts = json.loads(self.board("read", "--all", "--json", "--limit", "1000000", *scope) or "[]")
        locks = json.loads(self.board("locks", "--json") or "[]")
        live = {c["key"]: c for c in locks if c.get("live")}
        out: dict[str, dict] = {}
        for p in posts:
            ref = p.get("ref")
            if not ref or p.get("retracted") or p.get("kind") not in ("instruction", None):
                continue
            acks = p.get("acks") or []
            declined = any(a.get("state") == "declined" for a in acks)
            done = next((a for a in acks if a.get("state") == "done"), None)
            holder = next((live[k] for k in (p.get("task"), p.get("id"), ref) if k and k in live), None)
            if declined and not done:
                continue
            out[ref] = {"post": p["id"], "to": p.get("to"), "done": done, "holder": holder}
        # Open calls to any agent: the board's own view of a plan says when one is done (its task closed, or
        # the call marked done) and who holds it, which the posts alone do not.
        prefixes = {self.campaign} if self.campaign else {n["id"].split("-")[0] for n in self.nodes if "-" in n["id"]}
        for prefix in sorted(prefixes):
            for row in json.loads(self.board("plan", prefix, "--json", check=False) or "[]"):
                ref = row.get("ref")
                if not ref or not row.get("call"):
                    continue
                entry = out.setdefault(ref, {"post": row["call"], "to": ["any"], "done": None, "holder": None})
                if row.get("state") == "done":
                    entry["done"] = {"note": row.get("result") or "", "from": row.get("who")}
                    entry["holder"] = None
                elif row.get("state") == "held" and not entry["holder"]:
                    entry["holder"] = {"who": row.get("who"), "key": ref}
        for key, c in live.items():
            if key in self.by_id or key.startswith(f"{self.campaign}-" if self.campaign else "\0"):
                out.setdefault(key, {"post": None, "to": None, "done": None, "holder": c})
                out[key]["holder"] = out[key]["holder"] or c
        return out

    def held_in_chain(self, nid: str, state: dict[str, dict]) -> list[str]:
        """Nodes above or below nid that an agent holds: the edges a held node locks."""
        chain = self.ancestors(nid) + self.descendants(nid) + [nid]
        return sorted(x for x in chain if (state.get(self.ref(x)) or {}).get("holder"))

    # ---- commands

    def offer(self, dry: bool) -> int:
        state = self.board_state()
        posted = 0
        for n in self.nodes:
            nid = n["id"]
            ok, _ = self.startable(nid)
            if not ok or self.ref(nid) in state:
                continue
            to, kind = (f"runner:{n['runner']}", "instruction") if n.get("runner") else ("any", "instruction")
            text = self.call_text(n)
            if dry:
                print(f"would post {self.ref(nid)} to {to}: {text.splitlines()[0]}")
            else:
                args = ["post", text, "--to", to, "--kind", kind, "--ref", self.ref(nid)]
                if self.on:
                    args += ["--on", self.on]
                if self.source:
                    args += ["--source", self.source]
                if self.handle:
                    args += ["--as", self.handle]
                self.board(*args)
                print(f"posted {self.ref(nid)} to {to}")
            posted += 1
        print(f"{posted} node(s) {'to post' if dry else 'posted'}" + (f" in campaign {self.campaign}" if self.campaign else ""))
        return 0

    def call_text(self, n: dict) -> str:
        nid, hyp = n["id"], " ".join(str(n.get("hypothesis", "")).split())[:160]
        if self.campaign:
            return (f"{self.campaign} retest {nid}: {hyp}\n"
                    f"Retest this node's result in campaign {self.campaign}, as the research skill's "
                    f"references/pool.md (Retest campaign) says: replay its capsule, or rebuild the run if it has "
                    f"none, within the time box, then record the verdict with scripts/pool.py record {nid} "
                    f"--campaign {self.campaign} --verdict <reproduced|rebuilt|differs|unverifiable>. "
                    f"Close this call with the verdict and the capsule id.")
        return (f"{nid}: {hyp}\n"
                f"Take this hypothesis through the research skill (/research progress {nid}: frame it if it is "
                f"pending, run it, sync it), as references/pool.md (Worker) says. Every measured run goes through "
                f"vault.py run on the node's runtime. Close this call with the status and the capsule id.")

    def status(self) -> int:
        state = self.board_state()
        rows = {"held": [], "offered": [], "done": [], "ready": [], "waiting": []}
        for n in self.nodes:
            nid, ref = n["id"], self.ref(n["id"])
            s = state.get(ref)
            ok, why = self.startable(nid)
            if s and s["holder"]:
                rows["held"].append(f"{nid}  {s['holder']['who']}")
            elif s and s["done"]:
                rows["done"].append(f"{nid}  {s['done'].get('note', '')[:80]}")
            elif s:
                rows["offered"].append(f"{nid}  to {', '.join(s['to'] or [])}")
            elif ok:
                rows["ready"].append(f"{nid}  not yet posted")
            elif why.startswith("waits"):
                rows["waiting"].append(f"{nid}  {why}")
        title = f"Campaign {self.campaign}" if self.campaign else "Research pool"
        print(f"{title}: {len(rows['held'])} held, {len(rows['offered'])} offered, {len(rows['ready'])} ready to "
              f"post, {len(rows['waiting'])} waiting, {len(rows['done'])} done on the board")
        if self.campaign:
            counts = {v: 0 for v in VERDICTS}
            for n in self.nodes:
                v = self.verdict(n["id"])
                if v:
                    counts[v.get("verdict")] = counts.get(v.get("verdict"), 0) + 1
            scope = sum(1 for n in self.nodes if n.get("status") in RESULT)
            print(f"  verdicts: {', '.join(f'{k} {v}' for k, v in counts.items())} of {scope} result node(s)")
        for k in ("held", "offered", "ready", "waiting", "done"):
            for line in rows[k]:
                print(f"  {k:8} {line}")
        return 0

    def check(self, nid: str) -> int:
        if nid not in self.by_id:
            raise PoolError(f"{nid} is not in the DAG; refresh the view (dag_store.py view)")
        state = self.board_state()
        ok, why = self.startable(nid)
        held = [x for x in self.held_in_chain(nid, state) if x != nid]
        if held:
            print(f"no: {', '.join(held)} {'is' if len(held) == 1 else 'are'} held in {nid}'s chain; leave it "
                  f"until they are done")
            return 1
        if not ok:
            print(f"no: {nid} {why}")
            return 1
        mine = (state.get(self.ref(nid)) or {}).get("holder")
        print(f"yes: {nid} may be worked on" + (f" (held by {mine['who']})" if mine else ""))
        return 0

    def record(self, nid: str, verdict: str, capsule: str | None, note: str | None, agent: str | None) -> int:
        if not self.campaign:
            raise PoolError("record needs --campaign")
        if nid not in self.by_id:
            raise PoolError(f"{nid} is not in the DAG")
        if verdict in ("reproduced", "rebuilt", "differs") and not capsule:
            raise PoolError(f"a {verdict} verdict names the capsule it rests on (--capsule)")
        if verdict == "unverifiable" and not note:
            raise PoolError("an unverifiable verdict says what is missing (--note), so the node can be revisited")
        entry = {"campaign": self.campaign, "verdict": verdict, "at": now()}
        for k, v in (("capsule", capsule), ("note", note), ("by", agent)):
            if v:
                entry[k] = v
        tool = DAG_BIN / "dag_update.py"
        self._dag([sys.executable, str(tool), "--action", "append", "--node-id", nid, "--field", "retests",
                   "--value", json.dumps(entry)])
        if verdict == "differs" and self.by_id[nid].get("status") != "contested":
            self._dag([sys.executable, str(tool), "--action", "update", "--node-id", nid, "--status", "contested"])
            print(f"{nid} is now contested: its recorded result did not reproduce")
        print(f"Recorded {verdict} for {nid} in campaign {self.campaign}")
        return 0

    def _dag(self, cmd: list[str]) -> None:
        p = subprocess.run(cmd, cwd=self.cfg.repo_root, capture_output=True, text=True)
        if p.returncode != 0:
            raise PoolError(f"dag_update failed: {(p.stdout + p.stderr).strip()[:300]}")

    def review(self, as_json: bool, board: bool) -> int:
        """One snapshot of the hypotheses for a person or a view (mission control reads the JSON): every node
        with its status, result, evidence, where its latest capsule ran, its pool state and, in a campaign,
        its verdict; then what waits on the person. It knows nothing of the domain, so the same review serves
        basic research and trading models."""
        state: dict[str, dict] = {}
        board_error = None
        if board:
            try:
                state = self.board_state()
            except (PoolError, FileNotFoundError, json.JSONDecodeError) as e:
                board_error = str(e)[:300]
        nodes, by_status, pool_counts, verdicts = [], {}, {}, {}
        attention = []
        for n in self.nodes:
            nid = n["id"]
            status = str(n.get("status", "pending"))
            by_status[status] = by_status.get(status, 0) + 1
            caps = [c for c in n.get("capsules") or [] if isinstance(c, dict)]
            runs = [c for c in caps if c.get("kind") == "run"]
            latest = caps[-1] if caps else None
            s = state.get(self.ref(nid)) or {}
            ok, why = self.startable(nid)
            if s.get("holder"):
                pool_state = "held"
            elif s.get("done"):
                pool_state = "done"
            elif s:
                pool_state = "offered"
            elif ok:
                pool_state = "ready"
            elif why.startswith("waits"):
                pool_state = "waiting"
            else:
                pool_state = "settled"
            pool_counts[pool_state] = pool_counts.get(pool_state, 0) + 1
            verdict = self.verdict(nid) if self.campaign else None
            if verdict:
                verdicts[verdict.get("verdict")] = verdicts.get(verdict.get("verdict"), 0) + 1
            entry = {
                "id": nid, "parents": self.parents(n), "hypothesis": n.get("hypothesis"), "status": status,
                "metric": n.get("metric"), "target": n.get("target_improvement", n.get("target")),
                "actual": n.get("actual_performance"), "runtime": n.get("runtime"), "runner": n.get("runner"),
                "evidence": (runs[-1] if runs else latest or {}).get("evidence"),
                "capsules": len(caps),
                "latest_capsule": {k: latest.get(k) for k in ("id", "kind", "at", "verdict", "evidence", "env", "runtime",
                                                               "result") if latest.get(k) is not None} if latest else None,
                "pool": {"state": pool_state, "who": (s.get("holder") or {}).get("who"),
                         "waits_for": why[len("waits for "):].split(", ") if pool_state == "waiting" else [],
                         "result": (s.get("done") or {}).get("note")},
                "descendants": len(self.descendants(nid)),
            }
            if verdict:
                entry["verdict"] = {k: verdict.get(k) for k in ("verdict", "capsule", "note", "by", "at") if verdict.get(k)}
            nodes.append(entry)
            if status == "contested":
                attention.append({"node": nid, "level": "decision", "why": "contested: a retest, audit or parity "
                                  "replay disagrees with the recorded result"})
            if verdict and verdict.get("verdict") == "unverifiable":
                attention.append({"node": nid, "level": "look", "why": f"unverifiable in {self.campaign}: "
                                  f"{verdict.get('note', '')}", "descendants": entry["descendants"]})
            if status in RESULT and status != "contested" and not runs and n.get("runtime"):
                attention.append({"node": nid, "level": "look", "why": "a result with a runtime but no run capsule"})
        order = {"decision": 0, "look": 1}
        attention.sort(key=lambda a: (order[a["level"]], -a.get("descendants", 0), a["node"]))
        review = {"format": "research-review/1", "generated_at": now(), "project": self.cfg._get("dag_project", None),
                  "campaign": self.campaign, "board": None if not board else ({"error": board_error} if board_error else {"ok": True}),
                  "summary": {"nodes": len(nodes), "by_status": by_status, "pool": pool_counts,
                              **({"verdicts": verdicts, "in_scope": sum(1 for n in self.nodes if n.get("status") in RESULT)}
                                 if self.campaign else {})},
                  "attention": attention, "nodes": nodes}
        if as_json:
            print(json.dumps(review, indent=2, default=str))
            return 0
        sm = review["summary"]
        print(f"{len(nodes)} hypotheses · " + ", ".join(f"{k} {v}" for k, v in sorted(sm["by_status"].items())))
        print("pool: " + ", ".join(f"{k} {v}" for k, v in sorted(sm["pool"].items())))
        if self.campaign:
            print(f"campaign {self.campaign}: " + ", ".join(f"{k} {v}" for k, v in sorted(sm["verdicts"].items()))
                  + f" of {sm['in_scope']}")
        if board_error:
            print(f"board not read: {board_error}")
        for a in attention:
            print(f"  {'DECIDE' if a['level'] == 'decision' else 'look  '} {a['node']}: {a['why']}")
        return 0

    def revisit(self) -> int:
        if not self.campaign:
            raise PoolError("revisit needs --campaign")
        rows = []
        for n in self.nodes:
            v = self.verdict(n["id"])
            if v and v.get("verdict") == "unverifiable":
                below = self.descendants(n["id"])
                live = [d for d in below if self.by_id[d].get("status") not in ("discarded", "ineffective")]
                rows.append((len(live), len(below), n["id"], v.get("note", "")))
        if not rows:
            print(f"No unverifiable nodes in campaign {self.campaign}.")
            return 0
        rows.sort(key=lambda r: (-r[0], -r[1], r[2]))
        print(f"Unverifiable in {self.campaign}, the most depended on first (live descendants, all descendants):")
        for live, total, nid, note in rows:
            print(f"  {nid:16} {live:4} {total:4}  {note[:90]}")
        return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="The hypothesis pool on the board")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("offer", "status", "check", "record", "revisit", "review"):
        p = sub.add_parser(name)
        p.add_argument("--campaign", help="A retest campaign id, such as RT1")
        if name == "offer":
            p.add_argument("--dry-run", action="store_true")
        if name in ("check", "record"):
            p.add_argument("node")
        if name == "review":
            p.add_argument("--json", action="store_true", help="The snapshot as JSON, as mission control reads it")
            p.add_argument("--no-board", action="store_true", help="Read the DAG only, without the board")
        if name == "record":
            p.add_argument("--verdict", choices=VERDICTS, required=True)
            p.add_argument("--capsule")
            p.add_argument("--note")
            p.add_argument("--agent")
    args = ap.parse_args(argv)
    if args.campaign is not None and not args.campaign.replace("_", "").replace(".", "").isalnum():
        print("Error: a campaign id is letters and digits, such as RT1", file=sys.stderr)
        return 2
    try:
        pool = Pool(rms_config.load(), args.campaign)
        if args.cmd == "offer":
            return pool.offer(args.dry_run)
        if args.cmd == "review":
            return pool.review(args.json, not args.no_board)
        if args.cmd == "status":
            return pool.status()
        if args.cmd == "check":
            return pool.check(args.node)
        if args.cmd == "record":
            return pool.record(args.node, args.verdict, args.capsule, args.note, args.agent)
        return pool.revisit()
    except (PoolError, KeyError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
