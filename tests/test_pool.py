# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the hypothesis pool (skills/research/scripts/pool.py): what is offered on the board, how a held
node locks its chain, the retest campaign's top-down order and its verdicts. The board is a stand-in for
the thread skill's CLI that keeps its posts and claims in a JSON file, so the tests need neither Node nor
a store. Run from the repository root:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
POOL = REPO / "skills" / "research" / "scripts" / "pool.py"
DAG_UPDATE = REPO / "skills" / "research-dag" / "bin" / "dag_update.py"

FAKE_THREAD = textwrap.dedent("""\
    import json, sys
    from pathlib import Path
    state_file = Path(sys.argv[1])
    args = sys.argv[2:]
    s = json.loads(state_file.read_text()) if state_file.exists() else {"posts": [], "locks": []}
    def flag(name):
        return args[args.index(name) + 1] if name in args else None
    assert args[0] == "board", args
    cmd = args[1]
    if cmd == "read":
        print(json.dumps(s["posts"]))
    elif cmd == "locks":
        print(json.dumps(s["locks"]))
    elif cmd == "plan":
        prefix = args[2]
        rows = []
        for p in s["posts"]:
            ref = p.get("ref") or ""
            if "any" not in p["to"] or not (ref == prefix or ref.startswith(prefix + "-")):
                continue
            held = next((c for c in s["locks"] if c["live"] and c["key"] in (p["task"], p["id"], ref)), None)
            state = "done" if p.get("closed") else "held" if held else "offered"
            rows.append({"ref": ref, "call": p["id"], "task": p["task"], "state": state,
                         "who": held["who"] if held else None, "result": p.get("result")})
        print(json.dumps(rows))
    elif cmd == "post":
        n = len(s["posts"]) + 1
        to = flag("--to")
        s["posts"].append({"id": f"p-{n}", "task": f"t-{n}" if to == "any" else None, "to": [to],
                           "kind": flag("--kind"), "ref": flag("--ref"), "on": flag("--on"), "from": flag("--as"),
                           "text": args[2], "acks": []})
        state_file.write_text(json.dumps(s))
    else:
        sys.exit(f"fake thread: unsupported {args}")
    """)

DAG = textwrap.dedent("""\
    nodes:
    - {id: H-1, hypothesis: Root, status: validated, parent: null}
    - {id: H-1.1, hypothesis: Child a, status: pending, parent: H-1}
    - {id: H-1.2, hypothesis: Child b on the GPU, status: framed, parent: H-1, runner: local-gpu}
    - {id: H-1.1.1, hypothesis: Grandchild, status: pending, parent: H-1.1}
    - {id: H-1.3, hypothesis: Done already, status: ineffective, parent: H-1}
    - {id: H-2, hypothesis: Unresolved root, status: in_progress, parent: null}
    - {id: H-2.1, hypothesis: Under an open node, status: pending, parent: H-2}
    """)


class PoolTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name)
        (self.ws / "research").mkdir()
        (self.ws / "research" / "dag.yaml").write_text(DAG, encoding="utf-8")
        fake = self.ws / "fake_thread.py"
        fake.write_text(FAKE_THREAD, encoding="utf-8")
        self.board_file = self.ws / "board.json"
        (self.ws / "research.yaml").write_text(
            "dag_path: research/dag.yaml\nnode_index_path: research/index.yaml\nwork_items_path: work/\n"
            f"pool:\n  thread: '{Path(sys.executable).as_posix()} {fake.as_posix()} {self.board_file.as_posix()}'\n"
            "  on_thread: t-1\n  as: coordinator\n", encoding="utf-8")
        self.env = {k: v for k, v in os.environ.items() if k not in ("THREAD_CMD", "BOARD_AS", "RESEARCH_DAG_BIN")}

    def tearDown(self):
        self.tmp.cleanup()

    def pool(self, *args, check=True):
        p = subprocess.run([sys.executable, str(POOL), *args], cwd=self.ws, env=self.env, capture_output=True,
                           text=True)
        if check and p.returncode not in (0, 1):
            raise AssertionError(f"pool {args} failed ({p.returncode}):\n{p.stdout}\n{p.stderr}")
        return p

    def board(self):
        return json.loads(self.board_file.read_text()) if self.board_file.exists() else {"posts": [], "locks": []}

    def posts(self):
        return {p["ref"]: p for p in self.board()["posts"]}

    def claim(self, ref, who="agent-a"):
        s = self.board()
        post = next(p for p in s["posts"] if p["ref"] == ref)
        s["locks"].append({"key": post["task"] or post["id"], "who": who, "live": True})
        self.board_file.write_text(json.dumps(s))

    def finish(self, ref, status):
        s = self.board()
        for p in s["posts"]:
            if p["ref"] == ref:
                p["closed"] = True
                p["result"] = status
        s["locks"] = []
        self.board_file.write_text(json.dumps(s))
        if not ref.startswith("RT"):
            subprocess.run([sys.executable, str(DAG_UPDATE), "--action", "update", "--node-id", ref, "--status",
                            status], cwd=self.ws, env=self.env, capture_output=True, check=True)

    def dag(self):
        import yaml
        return {n["id"]: n for n in yaml.safe_load((self.ws / "research" / "dag.yaml").read_text())["nodes"]}


class TestResearchPool(PoolTestCase):
    def test_only_nodes_whose_parents_are_resolved_are_offered(self):
        p = self.pool("offer")
        self.assertIn("2 node(s) posted", p.stdout)
        posts = self.posts()
        self.assertEqual(sorted(posts), ["H-1.1", "H-1.2"])
        self.assertEqual(posts["H-1.1"]["to"], ["any"])
        self.assertEqual(posts["H-1.1"]["on"], "t-1")
        self.assertIn("/research progress H-1.1", posts["H-1.1"]["text"])

    def test_a_node_with_a_runner_goes_to_that_role_only(self):
        self.pool("offer")
        self.assertEqual(self.posts()["H-1.2"]["to"], ["runner:local-gpu"])

    def test_offering_twice_posts_nothing_new(self):
        self.pool("offer")
        p = self.pool("offer")
        self.assertIn("0 node(s) posted", p.stdout)
        self.assertEqual(len(self.board()["posts"]), 2)

    def test_a_held_node_locks_its_chain(self):
        self.pool("offer")
        self.claim("H-1.1")
        for nid in ("H-1", "H-1.1.1"):
            p = self.pool("check", nid)
            self.assertEqual(p.returncode, 1, nid)
            self.assertIn("H-1.1 is held", p.stdout)
        self.assertEqual(self.pool("check", "H-1.2").returncode, 0, "a sibling is not in the chain")
        self.assertIn("held 1", self.pool("status").stdout.replace("1 held", "held 1"))

    def test_a_finished_node_releases_its_children(self):
        self.pool("offer")
        self.claim("H-1.1")
        self.assertEqual(self.pool("check", "H-1.1.1").returncode, 1)
        self.finish("H-1.1", "validated")
        self.assertIn("posted H-1.1.1", self.pool("offer").stdout)
        self.assertEqual(self.pool("check", "H-1.1.1").returncode, 0)

    def test_status_shows_what_waits_and_on_what(self):
        self.pool("offer")
        out = self.pool("status").stdout
        self.assertIn("waiting  H-1.1.1  waits for H-1.1", out)
        self.assertIn("waiting  H-2.1  waits for H-2", out)


class TestCampaign(PoolTestCase):
    def test_a_campaign_retests_from_the_root_down(self):
        self.pool("offer", "--campaign", "RT1")
        self.assertEqual(sorted(self.posts()), ["RT1-H-1"], "only the root result is offered first")
        self.pool("record", "H-1", "--campaign", "RT1", "--verdict", "reproduced", "--capsule", "c-1")
        self.pool("offer", "--campaign", "RT1")
        self.assertEqual(sorted(self.posts()), ["RT1-H-1", "RT1-H-1.3"])
        self.assertIn("RT1 retest H-1.3", self.posts()["RT1-H-1.3"]["text"])

    def test_a_node_that_cannot_be_reproduced_does_not_block_its_children(self):
        (self.ws / "research" / "dag.yaml").write_text(DAG.replace("status: pending, parent: H-1}",
                                                                   "status: validated, parent: H-1}"),
                                                       encoding="utf-8")
        self.pool("record", "H-1", "--campaign", "RT1", "--verdict", "unverifiable",
                  "--note", "the data folder is gone")
        self.pool("offer", "--campaign", "RT1")
        self.assertIn("RT1-H-1.1", self.posts())
        self.assertEqual(self.dag()["H-1"]["status"], "validated", "unverifiable never changes the result")

    def test_a_verdict_names_its_capsule_or_what_is_missing(self):
        p = self.pool("record", "H-1", "--campaign", "RT1", "--verdict", "reproduced", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("names the capsule", p.stderr)
        p = self.pool("record", "H-1", "--campaign", "RT1", "--verdict", "unverifiable", check=False)
        self.assertIn("says what is missing", p.stderr)
        self.pool("record", "H-1", "--campaign", "RT1", "--verdict", "rebuilt", "--capsule", "c-2", "--agent", "a1")
        entry = self.dag()["H-1"]["retests"][0]
        self.assertEqual((entry["campaign"], entry["verdict"], entry["capsule"], entry["by"]), ("RT1", "rebuilt", "c-2", "a1"))

    def test_a_result_that_differs_makes_the_node_contested(self):
        self.pool("record", "H-1", "--campaign", "RT1", "--verdict", "differs", "--capsule", "c-3")
        self.assertEqual(self.dag()["H-1"]["status"], "contested")

    def test_revisit_lists_the_most_depended_on_first(self):
        self.pool("record", "H-1.3", "--campaign", "RT1", "--verdict", "unverifiable", "--note", "leaf")
        self.pool("record", "H-1", "--campaign", "RT1", "--verdict", "unverifiable", "--note", "root data lost")
        out = self.pool("revisit", "--campaign", "RT1").stdout
        self.assertLess(out.index("H-1 "), out.index("H-1.3"))
        self.assertIn("root data lost", out)

    def test_campaigns_are_kept_apart(self):
        self.pool("record", "H-1", "--campaign", "RT1", "--verdict", "reproduced", "--capsule", "c-1")
        self.pool("offer", "--campaign", "RT2")
        self.assertEqual(sorted(self.posts()), ["RT2-H-1"], "RT1's verdict does not settle RT2")


class TestReview(PoolTestCase):
    SCHEMA = json.loads((REPO / "skills" / "research" / "schemas" / "review.schema.json").read_text(encoding="utf-8"))

    def review(self, *args):
        data = json.loads(self.pool("review", "--json", *args).stdout)
        try:
            import jsonschema
            jsonschema.validate(data, self.SCHEMA)
        except ImportError:
            if os.environ.get("CI"):
                self.fail("jsonschema is not installed, so the review is not checked against its schema")
        return data

    def test_the_review_shows_every_node_with_its_pool_state(self):
        self.pool("offer")
        self.claim("H-1.1")
        r = self.review()
        nodes = {n["id"]: n for n in r["nodes"]}
        self.assertEqual(r["summary"]["nodes"], 7)
        self.assertEqual((nodes["H-1.1"]["pool"]["state"], nodes["H-1.1"]["pool"]["who"]), ("held", "agent-a"))
        self.assertEqual(nodes["H-1.2"]["pool"]["state"], "offered")
        self.assertEqual(nodes["H-1.1.1"]["pool"]["waits_for"], ["H-1.1"])
        self.assertEqual(nodes["H-1"]["descendants"], 4)

    def test_what_waits_on_a_person_comes_first(self):
        self.pool("record", "H-1.3", "--campaign", "RT1", "--verdict", "unverifiable", "--note", "lost")
        self.pool("record", "H-1", "--campaign", "RT1", "--verdict", "differs", "--capsule", "c-1")
        r = self.review("--campaign", "RT1")
        self.assertEqual([(a["node"], a["level"]) for a in r["attention"]], [("H-1", "decision"), ("H-1.3", "look")])
        self.assertEqual(r["summary"]["verdicts"], {"unverifiable": 1, "differs": 1})

    def test_the_review_works_without_a_board(self):
        self.env["THREAD_CMD"] = "no-such-thread-cli"
        r = self.review()
        self.assertIn("error", r["board"])
        r = self.review("--no-board")
        self.assertIsNone(r["board"])
        self.assertEqual({n["pool"]["state"] for n in r["nodes"]} - {"ready", "waiting", "settled"}, set())


if __name__ == "__main__":
    unittest.main()
