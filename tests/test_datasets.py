# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the vault's datasets: versions and their rules, windows, sealed holdouts, forward data, evidence
classes, and capsules that point at a dataset version instead of copying it. Run from the repository root:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_experiment_vault as tev  # noqa: E402

EVALUATE = textwrap.dedent("""\
    import glob, json, os
    spec = json.load(open(os.environ["VAULT_DATASETS"]))["prices"]
    rows = []
    for f in sorted(glob.glob(os.path.join(spec["path"], "*.csv"))):
        start = (spec["forward_offsets"] or {}).get(os.path.basename(f), 0)
        with open(f, "rb") as fh:
            fh.seek(start)
            rows += [line for line in fh.read().decode().splitlines() if line and not line.startswith("date")]
    window = spec["window"] or {}
    if window.get("from_date"):
        rows = [r for r in rows if window["from_date"] <= r.split(",")[0] <= window["to_date"]]
    if os.environ.get("TOUCH_DATA"):
        os.chmod(os.path.join(spec["path"], "AAA.csv"), 0o644)
        open(os.path.join(spec["path"], "AAA.csv"), "a").write("2026-01-09,1\\n")
    os.makedirs("out", exist_ok=True)
    json.dump({"rows": len(rows), "total": sum(float(r.split(",")[1]) for r in rows)}, open("out/metrics.json", "w"))
    """)

DAG = textwrap.dedent("""\
    nodes:
    - id: H-1
      hypothesis: Momentum predicts returns
      status: framed
      parent: null
    - id: H-1.1
      hypothesis: Ten-day momentum
      status: framed
      parent: H-1
    - id: H-1.2
      hypothesis: Twenty-day momentum
      status: framed
      parent: H-1
    - id: H-2
      hypothesis: Value predicts returns
      status: framed
      parent: null
    """)


class DatasetTestCase(tev.VaultTestCase):
    def setUp(self):
        super().setUp()
        self.env["RESEARCH_VAULT_CACHE"] = str(self.base / "cache")
        self.env.pop("CI", None)
        self.src = self.base / "src"
        self.src.mkdir()
        (self.src / "AAA.csv").write_text("date,close\n2026-01-01,10\n2026-01-02,11\n", encoding="utf-8", newline="\n")
        (self.exp / "evaluate.py").write_text(EVALUATE, encoding="utf-8", newline="\n")
        (self.exp / "research").mkdir()
        (self.exp / "research.yaml").write_text("dag_path: research/dag.yaml\nnode_index_path: research/index.yaml\n"
                                                "work_items_path: work/\n", encoding="utf-8", newline="\n")
        (self.exp / "research" / "dag.yaml").write_text(DAG, encoding="utf-8", newline="\n")
        with open(self.exp / ".gitignore", "a", encoding="utf-8") as f:
            f.write("research/\nresearch.yaml\nmounted/\n")
        tev.sh(["git", "add", "-A"], self.exp)
        tev.sh(["git", "commit", "-q", "-m", "evaluate"], self.exp)
        self.vault("init")

    def append(self, name, text):
        with open(self.src / name, "a", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def registered(self, rule="append-only"):
        self.vault("dataset", "create", "prices", "--rule", rule, "--source", "https://example.com/eod")
        self.vault("dataset", "add", "prices", "--from", str(self.src), "--note", "first pull")

    def evaluate(self, node, spec, *extra, check=True):
        p = self.vault("run", "--node", node, "--dataset", spec, "--outputs", "out", "--metrics", "out/metrics.json",
                       "--metric", "rows", "--no-link", *extra, "--", sys.executable, "evaluate.py", check=check)
        if not check:
            return p
        return p.stdout.split("Capsule ", 1)[1].split(":", 1)[0]

    def version(self, ref):
        name, version = ref.split("@")
        return json.loads((self.base / "vault" / "datasets" / name / "versions" / f"{version}.json").read_text("utf-8"))

    def as_person(self, *args, typed):
        """Run vault.py with a terminal on stdin, as a person would, typing `typed` at the prompt."""
        import pty
        leader, follower = pty.openpty()
        p = subprocess.Popen([sys.executable, str(tev.VAULT), *args], cwd=self.exp, env=self.env, stdin=follower,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        os.close(follower)
        os.write(leader, (typed + "\n").encode())
        out, err = p.communicate(timeout=120)
        os.close(leader)
        return p.returncode, out, err


class TestDatasetVersions(DatasetTestCase):
    def test_an_append_only_dataset_takes_new_files_and_extensions(self):
        self.registered()
        self.append("AAA.csv", "2026-01-03,12\n")
        (self.src / "BBB.csv").write_text("date,close\n2026-01-03,5\n", encoding="utf-8", newline="\n")
        p = self.vault("dataset", "add", "prices", "--from", str(self.src))
        self.assertIn("Added prices v0002: 1 added, 1 extended, 0 changed, 0 removed", p.stdout)
        v2 = self.version("prices@v0002")
        self.assertEqual(v2["parent"], "v0001")
        self.assertEqual(v2["changes"]["extended"], [{"path": "AAA.csv", "from_size": 39, "to_size": 53}])
        self.assertEqual(self.vault("dataset", "add", "prices", "--from", str(self.src)).stdout.strip(),
                         "No change from prices v0002; no version added.")

    def test_an_append_only_change_is_refused(self):
        self.registered()
        (self.src / "AAA.csv").write_text("date,close\n2026-01-01,99\n2026-01-02,11\n2026-01-03,12\n", encoding="utf-8", newline="\n")
        p = self.vault("dataset", "add", "prices", "--from", str(self.src), check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("changes or removes 1 file(s) of v0001: AAA.csv", p.stderr)
        (self.src / "AAA.csv").unlink()
        (self.src / "CCC.csv").write_text("x\n", encoding="utf-8", newline="\n")
        p = self.vault("dataset", "add", "prices", "--from", str(self.src), check=False)
        self.assertIn("changes or removes 1 file(s)", p.stderr, "a removed file is a change too")
        p = self.vault("dataset", "add", "prices", "--from", str(self.src), "--revise", "vendor fixed a price",
                       check=False)
        self.assertIn("is append-only: it is never revised", p.stderr)
        self.assertFalse((self.base / "vault" / "datasets" / "prices" / "versions" / "v0002.json").exists())

    def test_an_append_only_revision_needs_a_person(self):
        self.registered()
        (self.src / "AAA.csv").write_text("date,close\n2026-01-01,10.5\n2026-01-02,11\n", encoding="utf-8", newline="\n")
        args = ("dataset", "add", "prices", "--from", str(self.src), "--revise", "vendor fixed a price",
                "--allow-append-only-revision")
        p = self.vault(*args, check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("needs a person", p.stderr)
        self.env["CI"] = "true"
        if os.name != "nt":
            rc, _, err = self.as_person(*args, typed="prices")
            self.assertEqual(rc, 2, "CI is never a person, terminal or not")
            self.assertIn("needs a person", err)

    @unittest.skipIf(os.name == "nt", "the person is played through a POSIX terminal")
    def test_a_person_revises_and_is_shown_what_to_retest(self):
        self.registered()
        ref = self.evaluate("H-2", "prices@v0001:mounted/prices")
        (self.src / "AAA.csv").write_text("date,close\n2026-01-01,10.5\n2026-01-02,11\n", encoding="utf-8", newline="\n")
        args = ("dataset", "add", "prices", "--from", str(self.src), "--revise", "vendor fixed a price",
                "--allow-append-only-revision")
        rc, _, err = self.as_person(*args, typed="not-it")
        self.assertEqual(rc, 2)
        self.assertIn("not confirmed", err)
        rc, out, err = self.as_person(*args, typed="prices")
        self.assertEqual(rc, 0, err)
        self.assertIn(f"demo/{ref}", out)
        self.assertEqual(self.version("prices@v0002")["revision"], "vendor fixed a price")
        p = self.vault("dataset", "impact", "prices@v0002", "--strict", check=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn(f"demo/{ref}", p.stdout)

    def test_a_revisable_dataset_is_revised_with_a_reason(self):
        self.registered("revisable")
        (self.src / "AAA.csv").write_text("date,close\n2026-01-01,10.5\n", encoding="utf-8", newline="\n")
        p = self.vault("dataset", "add", "prices", "--from", str(self.src), check=False)
        self.assertIn("a change is a revision", p.stderr)
        self.vault("dataset", "add", "prices", "--from", str(self.src), "--revise", "cleaned outliers")
        self.assertEqual(self.version("prices@v0002")["changes"]["changed"], ["AAA.csv"])

    def test_a_frozen_dataset_takes_one_version(self):
        self.registered("frozen")
        self.append("AAA.csv", "2026-01-03,12\n")
        p = self.vault("dataset", "add", "prices", "--from", str(self.src), check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("is frozen", p.stderr)

    def test_a_dataset_and_its_versions_are_written_once(self):
        self.registered()
        p = self.vault("dataset", "create", "prices", "--rule", "revisable", check=False)
        self.assertIn("already exists", p.stderr)
        p = self.vault("dataset", "window", "prices", "w", "--class", "backtest", "--from-date", "2026-01-01",
                       "--to-date", "2026-01-01")
        p = self.vault("dataset", "window", "prices", "w", "--class", "backtest", "--from-date", "2026-01-01",
                       "--to-date", "2026-01-02", check=False)
        self.assertIn("a window is defined once", p.stderr)

    def test_a_version_records_its_provenance(self):
        sums = self.base / "SHA256SUMS"
        sums.write_text("abc  AAA.csv\n", encoding="utf-8", newline="\n")
        self.vault("dataset", "create", "prices", "--rule", "append-only", "--source", "https://example.com/eod",
                   "--licence", "CC-BY-4.0", "--owner", "research")
        self.vault("dataset", "add", "prices", "--from", str(self.src), "--source", "vendor pull 2026-01-02",
                   "--fetched-by", "fetch.py@abc123", "--source-checksums", str(sums), "--agent", "a1")
        desc = json.loads((self.base / "vault" / "datasets" / "prices" / "dataset.json").read_text("utf-8"))
        self.assertEqual(desc["sources"], ["https://example.com/eod"])
        self.assertEqual(desc["licence"], "CC-BY-4.0")
        v1 = self.version("prices@v0001")
        self.assertEqual((v1["source"], v1["fetched_by"], v1["agent"]), ("vendor pull 2026-01-02", "fetch.py@abc123", "a1"))
        self.assertIn("sha256", v1["source_checksums"])


class TestDatasetRuns(DatasetTestCase):
    def test_a_capsule_points_at_the_dataset_version_without_copying_it(self):
        self.registered()
        blobs = self.base / "vault" / "blobs" / "sha256"
        data_blob = self.version("prices@v0001")["files"]["AAA.csv"]["sha256"]
        ref = self.evaluate("H-2", "prices@latest:mounted/prices")
        m = self.manifest(ref)
        self.assertEqual(m["data"], [])
        self.assertEqual([(d["dataset"], d["version"], d["mount"]) for d in m["datasets"]],
                         [("prices", "v0001", "mounted/prices")])
        self.assertEqual(m["evidence"]["class"], "untracked")
        self.assertEqual(m["metrics"]["rows"], 2)
        self.assertEqual(sum(1 for b in blobs.iterdir() if b.name == data_blob), 1)
        cached = self.base / "cache" / "datasets" / "prices" / "v0001" / "AAA.csv"
        self.assertFalse(os.access(cached, os.W_OK) and os.name != "nt" and os.geteuid() != 0,
                         "cached data is read-only")
        p = self.vault("dataset", "uses", "prices")
        self.assertIn(f"demo/{ref}  v0001  untracked", p.stdout)

    def test_a_mount_that_is_not_git_ignored_is_refused(self):
        self.registered()
        p = self.evaluate("H-2", "prices@latest:tracked/prices", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("is not git-ignored", p.stderr)

    def test_a_run_that_writes_into_its_dataset_is_not_recorded(self):
        self.registered()
        self.env["TOUCH_DATA"] = "1"
        p = self.evaluate("H-2", "prices@latest:mounted/prices", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("the run changed dataset prices v0001", p.stderr)
        self.assertFalse((self.base / "vault" / "capsules" / "demo" / "H-2").exists())
        self.env.pop("TOUCH_DATA")
        ref = self.evaluate("H-2", "prices@latest:mounted/prices")
        self.assertEqual(self.manifest(ref)["metrics"]["rows"], 2, "the damaged cache is rebuilt from the vault")

    def test_verify_restore_and_replay_use_the_recorded_version(self):
        self.registered()
        ref = self.evaluate("H-2", "prices@v0001:mounted/prices")
        self.append("AAA.csv", "2026-01-03,12\n")
        self.vault("dataset", "add", "prices", "--from", str(self.src))
        self.vault("verify", ref, "--deep")
        tev.force_rmtree(self.base / "cache")
        p = self.vault("replay", ref, "--setup", "none", "--no-record", "--to", str(self.base / "replay"))
        self.assertIn("Verdict: identical", p.stdout)
        restored = self.base / "restored"
        self.vault("restore", ref, "--to", str(restored))
        self.assertEqual(sorted(os.listdir(restored / "repos" / "exp" / "mounted" / "prices")), [".vault-verified", "AAA.csv"])
        record = self.base / "vault" / "datasets" / "prices" / "versions" / "v0001.json"
        good = record.read_bytes()
        os.chmod(record, stat.S_IWUSR | stat.S_IRUSR)
        record.write_bytes(good.replace(b'"first pull"', b'"first pull!"'))
        p = self.vault("restore", ref, "--to", str(self.base / "restored-2"), check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("is not the version the capsule used", p.stderr)
        self.assertNotEqual(self.vault("verify", ref, check=False).returncode, 0)
        record.write_bytes(good)
        blob = self.version("prices@v0001")["files"]["AAA.csv"]["sha256"]
        os.chmod(self.base / "vault" / "blobs" / "sha256" / blob, stat.S_IWUSR | stat.S_IRUSR)
        (self.base / "vault" / "blobs" / "sha256" / blob).write_bytes(b"tampered")
        p = self.vault("verify", ref, "--deep", check=False)
        self.assertNotEqual(p.returncode, 0)

    def test_a_forward_window_gives_only_the_data_added_since(self):
        self.registered()
        self.vault("dataset", "window", "prices", "live", "--class", "forward", "--from-version", "v0001")
        p = self.evaluate("H-1.1", "prices@latest:mounted/prices:live", check=False)
        self.assertIn("holds no forward data yet", p.stderr)
        self.append("AAA.csv", "2026-01-03,12\n")
        (self.src / "BBB.csv").write_text("date,close\n2026-01-03,5\n", encoding="utf-8", newline="\n")
        self.vault("dataset", "add", "prices", "--from", str(self.src))
        m = self.manifest(self.evaluate("H-1.1", "prices@latest:mounted/prices:live"))
        self.assertEqual(m["evidence"]["class"], "forward")
        self.assertEqual(m["datasets"][0]["forward_offsets"], {"AAA.csv": 39, "BBB.csv": 0})
        self.assertEqual((m["metrics"]["rows"], m["metrics"]["total"]), (2, 17.0))

    def test_a_forward_window_needs_an_append_only_dataset(self):
        self.registered("revisable")
        p = self.vault("dataset", "window", "prices", "live", "--class", "forward", "--from-version", "v0001",
                       check=False)
        self.assertIn("needs an append-only dataset", p.stderr)

    def test_one_test_has_one_evidence_class(self):
        self.registered()
        self.vault("dataset", "window", "prices", "train", "--class", "backtest", "--from-date", "2026-01-01",
                   "--to-date", "2026-01-01")
        self.vault("dataset", "create", "rates", "--rule", "append-only")
        self.vault("dataset", "add", "rates", "--from", str(self.src))
        self.vault("dataset", "window", "rates", "live", "--class", "forward", "--from-version", "v0001")
        self.append("AAA.csv", "2026-01-03,12\n")
        self.vault("dataset", "add", "rates", "--from", str(self.src))
        p = self.vault("run", "--node", "H-2", "--dataset", "prices@latest:mounted/prices:train",
                       "--dataset", "rates@latest:mounted/rates:live", "--no-link", "--", sys.executable,
                       "evaluate.py", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("one test has one evidence class", p.stderr)

    def test_the_node_records_each_capsules_evidence_class(self):
        self.registered()
        self.env["RESEARCH_DAG_BIN"] = str(tev.DAG_BIN)
        self.vault("run", "--node", "H-2", "--dataset", "prices@latest:mounted/prices", "--outputs", "out",
                   "--metrics", "out/metrics.json", "--metric", "rows", "--", sys.executable, "evaluate.py")
        import yaml
        dag = yaml.safe_load((self.exp / "research" / "dag.yaml").read_text(encoding="utf-8"))
        node = next(n for n in dag["nodes"] if n["id"] == "H-2")
        self.assertEqual(node["capsules"][0]["evidence"], "untracked")

    def test_an_exploratory_run_is_never_evidence(self):
        self.registered()
        self.vault("dataset", "window", "prices", "train", "--class", "backtest", "--from-date", "2026-01-01",
                   "--to-date", "2026-01-01")
        m = self.manifest(self.evaluate("H-2", "prices@latest:mounted/prices:train", "--exploratory"))
        self.assertEqual(m["evidence"]["class"], "exploratory")
        self.assertEqual(m["evidence"]["windows"], [{"dataset": "prices", "window": "train", "class": "backtest"}])


class TestHoldouts(DatasetTestCase):
    def setUp(self):
        super().setUp()
        self.registered()
        self.vault("dataset", "window", "prices", "sealed", "--class", "holdout", "--from-date", "2026-01-02",
                   "--to-date", "2026-01-02")

    def claims(self):
        folder = self.base / "vault" / "datasets" / "prices" / "windows" / "sealed" / "claims"
        return sorted(os.listdir(folder)) if folder.exists() else []

    def test_a_holdout_gives_each_node_one_look(self):
        m = self.manifest(self.evaluate("H-1.1", "prices@latest:mounted/prices:sealed"))
        self.assertEqual(m["evidence"]["class"], "holdout")
        self.assertEqual(m["metrics"]["rows"], 1)
        self.assertEqual(self.claims(), ["H-1.1.json"])
        p = self.evaluate("H-1.1", "prices@latest:mounted/prices:sealed", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("already looked at by H-1.1 (this node)", p.stderr)
        self.assertEqual(len(os.listdir(self.base / "vault" / "capsules" / "demo" / "H-1.1")), 1)
        self.evaluate("H-2", "prices@latest:mounted/prices:sealed")
        p = self.evaluate("H-2", "prices@latest:mounted/prices:sealed", check=False)
        self.assertIn("already looked at by H-2 (this node)", p.stderr, "a node with no parent has one look too")

    def test_a_sibling_cannot_look_at_a_holdout_its_sibling_saw(self):
        self.evaluate("H-1.1", "prices@latest:mounted/prices:sealed")
        p = self.vault("run", "--node", "H-1.2", "--dataset", "prices@latest:mounted/prices:sealed", "--dry-run",
                       "--", sys.executable, "evaluate.py", check=False)
        self.assertIn("PROBLEM holdout sealed of prices was already looked at by H-1.1 (a sibling of this node)",
                      p.stdout)
        p = self.evaluate("H-1.2", "prices@latest:mounted/prices:sealed", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("a sibling of this node", p.stderr)
        self.evaluate("H-2", "prices@latest:mounted/prices:sealed")
        self.assertEqual(self.claims(), ["H-1.1.json", "H-2.json"], "a node with another parent may look")

    def test_a_dry_run_does_not_spend_the_look(self):
        self.vault("run", "--node", "H-1.1", "--dataset", "prices@latest:mounted/prices:sealed", "--dry-run",
                   "--", sys.executable, "evaluate.py")
        self.assertEqual(self.claims(), [])
        self.assertFalse((self.exp / "mounted").exists())

    def test_a_holdout_needs_the_node_in_the_dag(self):
        p = self.evaluate("H-9", "prices@latest:mounted/prices:sealed", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("H-9 is not in the DAG", p.stderr)
        self.assertEqual(self.claims(), [])

    def test_a_dataset_with_a_holdout_is_read_through_a_window(self):
        p = self.evaluate("H-2", "prices@latest:mounted/prices", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("has a sealed holdout, so a run on it names its window", p.stderr)
        p = self.vault("dataset", "window", "prices", "train", "--class", "backtest", "--from-date", "2026-01-01",
                       "--to-date", "2026-01-02", check=False)
        self.assertIn("overlaps holdout window sealed", p.stderr)
        self.vault("dataset", "window", "prices", "train", "--class", "backtest", "--from-date", "2026-01-01",
                   "--to-date", "2026-01-01")
        m = self.manifest(self.evaluate("H-2", "prices@latest:mounted/prices:train"))
        self.assertEqual((m["evidence"]["class"], m["metrics"]["rows"]), ("backtest", 1))

    def test_overriding_a_holdout_needs_a_person(self):
        self.evaluate("H-1.1", "prices@latest:mounted/prices:sealed")
        p = self.evaluate("H-1.2", "prices@latest:mounted/prices:sealed", "--override-holdout", "rerun", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("needs a person", p.stderr)
        self.assertEqual(self.claims(), ["H-1.1.json"])

    @unittest.skipIf(os.name == "nt", "the person is played through a POSIX terminal")
    def test_a_persons_override_is_recorded(self):
        self.evaluate("H-1.1", "prices@latest:mounted/prices:sealed")
        rc, out, err = self.as_person("run", "--node", "H-1.2", "--dataset", "prices@latest:mounted/prices:sealed",
                                      "--override-holdout", "the first look used a broken loader", "--outputs", "out",
                                      "--metrics", "out/metrics.json", "--no-link", "--", sys.executable,
                                      "evaluate.py", typed="prices")
        self.assertEqual(rc, 0, err)
        override = [c for c in self.claims() if "override" in c]
        self.assertEqual(len(override), 1)
        claim = json.loads((self.base / "vault" / "datasets" / "prices" / "windows" / "sealed" / "claims"
                            / override[0]).read_text("utf-8"))
        self.assertEqual(claim["override"], "the first look used a broken loader")
        p = self.vault("dataset", "uses", "prices", "--window", "sealed")
        self.assertIn("claim  H-1.2  (parent H-1)", p.stdout)
        self.assertIn("OVERRIDE: the first look used a broken loader", p.stdout)

    def test_a_replay_of_a_holdout_result_is_not_a_new_look(self):
        ref = self.evaluate("H-1.1", "prices@latest:mounted/prices:sealed")
        p = self.vault("replay", ref, "--setup", "none", "--no-link", "--to", str(self.base / "replay"))
        self.assertIn("Verdict: identical", p.stdout)
        self.assertEqual(self.claims(), ["H-1.1.json"])


class TestProtocol(unittest.TestCase):
    """The protocol quotes the tool's refusals so agents can match them; every quote must still be one."""

    def test_every_quoted_refusal_is_one_the_tool_gives(self):
        page = (tev.VAULT.parents[1] / "references" / "protocol.md").read_text(encoding="utf-8")
        source = tev.VAULT.read_text(encoding="utf-8")
        quotes, inside = [], False
        for line in page.splitlines():
            if line.startswith("| The tool says"):
                inside = True
            elif not line.startswith("|"):
                inside = False
            elif inside and line.startswith("| `"):
                quotes += re.findall(r"`([^`]+)`", line.split("|")[1])
        self.assertGreaterEqual(len(quotes), 20)
        for q in quotes:
            fixed = [part for part in re.split(r"<[^>]+>|\.\.\.", q) if part.strip()]
            for part in fixed:
                self.assertIn(part.strip(" .()"), source, f"the protocol quotes {q!r}, which vault.py never says")


if __name__ == "__main__":
    unittest.main()
