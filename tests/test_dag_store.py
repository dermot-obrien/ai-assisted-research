# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the shared DAG store and dag_update's use of it.

Every store here is a local bare repository in a temporary directory, so the
tests need git but no network. Run from the repository root:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import copy
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
BIN = REPO / "skills" / "research-dag" / "bin"
sys.path.insert(0, str(BIN))

import dag_store  # noqa: E402
import dag_update  # noqa: E402

FIXTURE = textwrap.dedent("""\
    # Hypothesis DAG for a test project
    #
    # STATUS KEY: pending, in_progress, validated, ineffective

    project:
      name: "Test project"
      started: 2026-01-31
      thresholds: {1: low, 2: high}

      # A comment inside the project block, above the nodes.
    nodes:
      # === ROOT ===
      - id: H-000
        parent: null
        hypothesis: "The root idea."
        status: validated
        actual_performance:
          accuracy: 1.000
        notes: |
          First line.
          Second line.

      # === BRANCH ONE ===
      - id: H-100
        parent: H-000
        hypothesis: "A first branch."
        status: validated
        avenues: [H-101]

      - id: H-101
        parent: H-100
        hypothesis: "A leaf under the first branch."
        status: pending
        target_improvement: 0.50
        adoption:
          state: not_assessed
          verified_on: null

      - id: H-204
        parent: H-000
        hypothesis: "A hierarchical parent."
        status: in_progress
        tags: [a, b]

      - id: H-204.1
        parent: H-204
        hypothesis: "Its first child."
        status: ineffective

      - id: H-204.2a
        parent: H-204
        hypothesis: "A letter-suffixed child."
        status: discarded
    """)


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


class StoreCase(unittest.TestCase):
    """A temporary directory holding a bare store, clones and workspaces."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dagstore-"))
        self.bare = self.tmp / "store.git"
        git("init", "--quiet", "--bare", "-b", "main", str(self.bare), cwd=self.tmp)
        self.fixture = self.tmp / "fixture.yaml"
        self.fixture.write_text(FIXTURE, encoding="utf-8")
        self.env = {**os.environ, "RESEARCH_DAG_HOME": str(self.tmp / "home")}
        self.env.pop("RMS_ROOT", None)

    def tearDown(self):
        def unlock(func, path, _):
            os.chmod(path, 0o700)
            func(path)
        shutil.rmtree(self.tmp, onerror=unlock)

    def clone(self, name, project="demo"):
        store = dag_store.DagStore(self.tmp / name, project, remote=str(self.bare))
        store.ensure()
        store.pull()
        return store

    def seeded(self, name="a"):
        store = self.clone(name)
        store.init_files()
        dag_store.import_dag(store, self.fixture)
        self.assertTrue(store.commit_and_push("import"))
        return store

    def workspace(self, name, store_keys=True, dag_text=None):
        ws = self.tmp / name
        (ws / "research").mkdir(parents=True)
        text = (REPO / "skills" / "research-dag" / "assets" / "research.yaml.example").read_text(encoding="utf-8")
        if store_keys:
            text += f'\ndag_store: "{self.bare.as_posix()}"\ndag_project: demo\n'
        (ws / "research.yaml").write_text(text, encoding="utf-8")
        if dag_text is not None:
            (ws / "research" / "hypothesis-dag.yaml").write_text(dag_text, encoding="utf-8")
        return ws

    def run_tool(self, ws, tool, *args, env=None, check=True):
        r = subprocess.run([sys.executable, str(BIN / tool), *args], cwd=str(ws), env=env or self.env,
                           capture_output=True, text=True, encoding="utf-8")
        if check and r.returncode != 0:
            self.fail(f"{tool} {' '.join(args)} failed ({r.returncode}):\n{r.stdout}\n{r.stderr}")
        return r


def begin_change(store):
    """The first half of a dag_update write: pull, replay, and a copy to change."""
    store.pull()
    before = store.replay().to_dag()
    return before, copy.deepcopy(before)


def finish_change(store, before, after):
    """The second half: diff into events, and push with the collision check on rebase."""
    written = store.write_events(dag_store.diff_events(before, after))
    pushed = store.commit_and_push("change", on_rebase=lambda: written.extend(store.resolve_collisions(written)))
    return written, pushed


class RoundTrip(StoreCase):

    def test_import_replays_to_the_same_content_and_order(self):
        store = self.seeded()
        original = yaml.safe_load(FIXTURE)
        replayed = store.replay().to_dag()
        self.assertEqual(replayed, original)
        self.assertEqual(dag_store.compare(replayed, original), [])
        self.assertEqual([n["id"] for n in replayed["nodes"]], [n["id"] for n in original["nodes"]])
        for a, b in zip(replayed["nodes"], original["nodes"]):
            self.assertEqual(list(a), list(b))
        self.assertIsInstance(replayed["project"]["started"], dt.date)
        self.assertEqual(replayed["project"]["thresholds"], {1: "low", 2: "high"})

    def test_one_event_per_node(self):
        store = self.seeded()
        events = store.events()
        self.assertEqual([e["type"] for e in events].count("add"), 6)
        self.assertEqual([e["type"] for e in events].count("doc"), 1)

    def test_the_view_loads_to_the_same_content_and_keeps_comments(self):
        store = self.seeded()
        view = self.tmp / "view.yaml"
        store.write_view(view)
        text = view.read_text(encoding="utf-8")
        self.assertEqual(yaml.safe_load(text), yaml.safe_load(FIXTURE))
        for comment in ("# Hypothesis DAG for a test project", "# === BRANCH ONE ===",
                        "# A comment inside the project block"):
            self.assertIn(comment, text)
        self.assertIn("  notes: |", text.replace("    notes: |", "  notes: |"))
        self.assertEqual(dag_store.view_commit(text), store.head())

    def test_a_second_import_is_refused(self):
        self.seeded()
        ws = self.workspace("ws")
        r = self.run_tool(ws, "dag_store.py", "import", "--from", str(self.fixture), check=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("already has events", r.stderr)

    def test_import_and_verify_from_the_command_line(self):
        ws = self.workspace("ws")
        self.run_tool(ws, "dag_store.py", "import", "--from", str(self.fixture))
        r = self.run_tool(ws, "dag_store.py", "verify", "--against", str(self.fixture))
        self.assertIn("reproduces", r.stdout)
        self.run_tool(ws, "dag_store.py", "view")
        view = yaml.safe_load((ws / "research" / "hypothesis-dag.yaml").read_text(encoding="utf-8"))
        self.assertEqual(view, yaml.safe_load(FIXTURE))


class Ids(unittest.TestCase):

    def ids(self):
        return [n["id"] for n in yaml.safe_load(FIXTURE)["nodes"]]

    def test_dotted_children_continue(self):
        self.assertEqual(dag_update.hierarchical_child_id(self.ids(), "H-204"), "H-204.3")

    def test_a_block_parent_takes_the_next_flat_id(self):
        self.assertEqual(dag_update.hierarchical_child_id(self.ids(), "H-100"), "H-102")

    def test_the_root_takes_the_next_block(self):
        self.assertEqual(dag_update.hierarchical_child_id(self.ids(), "H-000"), "H-200")

    def test_a_leaf_starts_a_dotted_level(self):
        self.assertEqual(dag_update.hierarchical_child_id(self.ids(), "H-101"), "H-101.1")

    def test_an_unknown_parent_is_refused(self):
        with self.assertRaises(ValueError):
            dag_update.hierarchical_child_id(self.ids(), "H-999")

    def test_a_flat_dag_keeps_sequential_numbering(self):
        nodes = [{"id": "H-000"}, {"id": "H-001"}, {"id": "H-007"}]
        self.assertEqual(dag_update.next_node_id(nodes, "H-001"), "H-008")


class Concurrency(StoreCase):

    def test_concurrent_adds_of_the_same_id_alias_the_later_push(self):
        a = self.seeded("a")
        b = self.clone("b")
        # B allocates first and writes first, but A pushes first.
        b_before, b_after = begin_change(b)
        b_id = dag_update.add_node(b_after, "H-204", "B's idea", 0.1)
        b_written = b.write_events(dag_store.diff_events(b_before, b_after))
        a_before, a_after = begin_change(a)
        a_id = dag_update.add_node(a_after, "H-204", "A's idea", 0.1)
        self.assertEqual(a_id, b_id)
        _, pushed = finish_change(a, a_before, a_after)
        self.assertTrue(pushed)
        pushed = b.commit_and_push("change", on_rebase=lambda: b_written.extend(b.resolve_collisions(b_written)))
        self.assertTrue(pushed)

        for store in (a, b):
            store.pull()
            state = store.replay()
            self.assertEqual(state.nodes[a_id]["hypothesis"], "A's idea")
            self.assertEqual(state.nodes[a_id + "b"]["hypothesis"], "B's idea")
            self.assertEqual(state.nodes[a_id + "b"]["id"], a_id + "b")
            self.assertEqual([(x["id"], x["was"], x["recorded"]) for x in state.aliases],
                             [(a_id + "b", a_id, True)])
            self.assertIn(a_id + "b", state.nodes["H-204"]["avenues"])
            self.assertIn(a_id, state.nodes["H-204"]["avenues"])
        view = self.tmp / "view.yaml"
        a.write_view(view)
        self.assertIn(f"# alias: added as {a_id}", view.read_text(encoding="utf-8"))

    def test_an_unrecorded_duplicate_keeps_the_earlier_and_suffixes_the_later(self):
        a = self.seeded("a")
        a.write_events([{"type": "add", "id": "H-300", "node": {"id": "H-300", "hypothesis": "first"}}])
        a.write_events([{"type": "add", "id": "H-300", "node": {"id": "H-300", "hypothesis": "second"}}])
        state = a.replay()
        self.assertEqual(state.nodes["H-300"]["hypothesis"], "first")
        self.assertEqual(state.nodes["H-300b"]["hypothesis"], "second")
        self.assertFalse(state.aliases[0]["recorded"])

    def test_concurrent_field_edits_later_wins_and_the_replaced_value_is_reported(self):
        a = self.seeded("a")
        b = self.clone("b")
        a_before, a_after = begin_change(a)
        b_before, b_after = begin_change(b)
        dag_update.update_node_status(a_after, "H-101", "in_progress")
        dag_update.update_node_status(b_after, "H-101", "ineffective")
        finish_change(a, a_before, a_after)
        _, pushed = finish_change(b, b_before, b_after)
        self.assertTrue(pushed)
        a.pull()
        state = a.replay()
        self.assertEqual(state.nodes["H-101"]["status"], "ineffective")
        self.assertEqual(len(state.conflicts), 1)
        c = state.conflicts[0]
        self.assertEqual((c["id"], c["field"], c["replaced"], c["value"]),
                         ("H-101", "status", "in_progress", "ineffective"))
        view = self.tmp / "view.yaml"
        a.write_view(view, state)
        self.assertIn('# concurrent edit: status was "in_progress"', view.read_text(encoding="utf-8"))

    def test_sequential_edits_are_not_conflicts(self):
        a = self.seeded("a")
        for status in ("in_progress", "validated"):
            before, after = begin_change(a)
            dag_update.update_node_status(after, "H-101", status)
            finish_change(a, before, after)
        state = a.replay()
        self.assertEqual(state.nodes["H-101"]["status"], "validated")
        self.assertEqual(state.conflicts, [])

    def test_concurrent_notes_on_a_list_both_survive(self):
        a = self.seeded("a")
        b = self.clone("b")
        a_before, a_after = begin_change(a)
        b_before, b_after = begin_change(b)
        dag_update.add_note(a_after, "H-204", "from a")
        dag_update.add_note(b_after, "H-204", "from b")
        finish_change(a, a_before, a_after)
        finish_change(b, b_before, b_after)
        a.pull()
        self.assertEqual(a.replay().nodes["H-204"]["notes"], ["from a", "from b"])


class Prune(StoreCase):

    def test_prune_archives_closed_nodes_and_replay_still_reads_them(self):
        a = self.seeded("a")
        before = a.replay().to_dag()
        state = a.replay()
        closed = a.closed_nodes(state, days=-1, statuses=dag_store.DEFAULT_CLOSED)
        self.assertEqual(set(closed), {"H-000", "H-100", "H-204.1", "H-204.2a"})
        r = a.archive(closed, state)
        self.assertEqual(r["events"], 4)
        a.commit_and_push("prune")
        self.assertEqual(len(list((a.dir / "events").rglob("*.json"))), 3)
        self.assertEqual(a.replay().to_dag(), before)
        # An archived node can still change.
        b_before, b_after = begin_change(a)
        dag_update.update_node_status(b_after, "H-100", "contested")
        finish_change(a, b_before, b_after)
        self.assertEqual(a.replay().nodes["H-100"]["status"], "contested")

    def test_prune_leaves_recent_nodes(self):
        a = self.seeded("a")
        self.assertEqual(a.closed_nodes(a.replay(), days=30, statuses=dag_store.DEFAULT_CLOSED), [])


class Record(StoreCase):

    def test_edits_to_the_view_become_events_without_reverting_newer_pushes(self):
        self.seeded("a")
        ws = self.workspace("ws")
        self.run_tool(ws, "dag_store.py", "view")
        # Someone else changes a node after the view was generated.
        other = self.clone("other")
        before, after = begin_change(other)
        dag_update.update_node_status(after, "H-204", "validated")
        finish_change(other, before, after)
        # A tool edits the view directly.
        path = ws / "research" / "hypothesis-dag.yaml"
        text = path.read_text(encoding="utf-8").replace("target_improvement: 0.5", "target_improvement: 0.25")
        path.write_text(text, encoding="utf-8")
        self.run_tool(ws, "dag_store.py", "record")
        other.pull()
        nodes = other.replay().nodes
        self.assertEqual(nodes["H-101"]["target_improvement"], 0.25)
        self.assertEqual(nodes["H-204"]["status"], "validated")


class DagUpdateCli(StoreCase):

    def test_without_store_keys_the_yaml_file_is_edited_as_before(self):
        flat = "nodes:\n- id: H-001\n  hypothesis: Root idea\n  status: framed\n  parents: []\n"
        ws = self.workspace("ws", store_keys=False, dag_text=flat)
        r = self.run_tool(ws, "dag_update.py", "--dag", "research/hypothesis-dag.yaml", "--action", "add",
                          "--parent", "H-001", "--hypothesis", "A variant", "--target", "0.05")
        self.assertIn("Added new node: H-002", r.stdout)
        dag = yaml.safe_load((ws / "research" / "hypothesis-dag.yaml").read_text(encoding="utf-8"))
        self.assertEqual([n["id"] for n in dag["nodes"]], ["H-001", "H-002"])
        self.assertFalse((self.tmp / "home").exists())

    def test_with_store_keys_changes_go_to_the_store_and_the_view_is_regenerated(self):
        self.seeded("a")
        ws = self.workspace("ws")
        r = self.run_tool(ws, "dag_update.py", "--action", "add", "--parent", "H-204",
                          "--hypothesis", "Store idea", "--target", "0.05")
        self.assertIn("Added new node: H-204.3", r.stdout)
        self.run_tool(ws, "dag_update.py", "--action", "update", "--node-id", "H-204.3", "--status", "in_progress")
        self.run_tool(ws, "dag_update.py", "--action", "relink", "--node-id", "H-204.3", "--parent", "H-100")
        self.run_tool(ws, "dag_update.py", "--action", "set", "--node-id", "H-204.3", "--field", "evidence",
                      "--value", "see run 12")
        self.run_tool(ws, "dag_update.py", "--action", "note", "--node-id", "H-204.3", "--note", "checked")
        view = yaml.safe_load((ws / "research" / "hypothesis-dag.yaml").read_text(encoding="utf-8"))
        node = next(n for n in view["nodes"] if n["id"] == "H-204.3")
        self.assertEqual((node["status"], node["parent"], node["evidence"], node["notes"]),
                         ("in_progress", "H-100", "see run 12", ["checked"]))
        a = self.clone("a")
        a.pull()
        self.assertEqual(a.replay().to_dag(), view)
        # The reading tools work on the view unchanged.
        self.run_tool(ws, "generate_node_index.py")
        self.run_tool(ws, "validate_dag_references.py")

    def test_validate_reports_aliases(self):
        a = self.seeded("a")
        a.write_events([{"type": "add", "id": "H-300", "node": {"id": "H-300", "parent": "H-000"}}])
        a.write_events([{"type": "add", "id": "H-300", "node": {"id": "H-300", "parent": "H-000"}}])
        a.commit_and_push("duplicate")
        ws = self.workspace("ws")
        self.run_tool(ws, "dag_store.py", "view")
        r = self.run_tool(ws, "validate_dag_references.py")
        self.assertIn("H-300b was added as H-300", r.stdout)
        r = self.run_tool(ws, "dag_store.py", "report")
        self.assertIn("H-300b was added as H-300", r.stdout)


if __name__ == "__main__":
    unittest.main()
