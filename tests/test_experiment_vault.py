# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the experiment vault: capture, verify, restore, replay and the DAG link.

Every vault here is a temporary folder, and the gs:// backend runs against a fake
gcloud that maps a bucket to a folder, so the tests need git but no network. Run
from the repository root:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VAULT = REPO / "skills" / "experiment-vault" / "bin" / "vault.py"
DAG_BIN = REPO / "skills" / "research-dag" / "bin"
sys.path.insert(0, str(VAULT.parent))

import vault  # noqa: E402

TRAIN = textwrap.dedent("""\
    import json, os, random, sys
    seed = int(sys.argv[sys.argv.index("--seed") + 1])
    random.seed(seed)
    values = [float(x) for x in open("data/raw.csv").read().split()]
    score = sum(v * random.random() for v in values) / len(values)
    if os.environ.get("DRIFT"):
        score += 0.5
    os.makedirs("out", exist_ok=True)
    json.dump({"score": score, "n": len(values)}, open("out/metrics.json", "w"))
    open("out/pred.txt", "w").write(f"{score:.12f}\\n")
    print("score", score)
    """)

FAKE_GCLOUD = textwrap.dedent("""\
    #!/usr/bin/env python3
    # A stand-in for `gcloud storage` that maps gs://<bucket>/ to $FAKE_GCS/<bucket>/.
    import os, shutil, sys
    from pathlib import Path
    ROOT = Path(os.environ["FAKE_GCS"])
    def local(url):
        return ROOT / url[len("gs://"):]
    args = sys.argv[1:]
    assert args[0] == "storage", args
    cmd, rest = args[1], args[2:]
    flags = [a for a in rest if a.startswith("-")]
    pos = [a for a in rest if not a.startswith("-")]
    if cmd == "cat":
        p = local(pos[0])
        if not p.is_file():
            sys.stderr.write("ERROR: No URLs matched\\n"); sys.exit(1)
        sys.stdout.buffer.write(p.read_bytes()); sys.exit(0)
    if cmd == "objects" and rest[0] == "describe":
        sys.exit(0 if local(rest[1]).is_file() else 1)
    if cmd == "ls":
        found = False
        for url in pos:
            if url.endswith("**"):
                base = local(url[:-2])
                for f in sorted(base.rglob("*")) if base.exists() else []:
                    if f.is_file():
                        print("gs://" + f.relative_to(ROOT).as_posix()); found = True
            elif local(url).is_file():
                print(url); found = True
            else:
                sys.stderr.write(f"ERROR: {url} not found\\n")
        sys.exit(0 if found else 1)
    if cmd == "cp":
        srcs = [l.strip() for l in sys.stdin if l.strip()] if "-I" in flags else pos[:-1]
        dest = pos[-1]
        for src in srcs:
            if dest.startswith("gs://"):
                target = local(dest + Path(src).name) if dest.endswith("/") else local(dest)
                if target.exists() and ("--no-clobber" in flags or "--if-generation-match=0" in flags):
                    if "--if-generation-match=0" in flags:
                        sys.stderr.write("PreconditionFailed 412\\n"); sys.exit(1)
                    sys.stderr.write(f"Skipping existing destination item (no-clobber): {dest}\\n")
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, target)
            else:
                d = Path(dest)
                d.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(local(src), d / src.rsplit("/", 1)[-1])
        sys.exit(0)
    sys.stderr.write(f"fake gcloud: unsupported {args}\\n"); sys.exit(2)
    """)


def sh(args, cwd, env=None, check=True):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)
    if check and p.returncode != 0:
        raise AssertionError(f"{args} failed ({p.returncode}):\n{p.stdout}\n{p.stderr}")
    return p


class VaultTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.exp = self.base / "exp"
        (self.exp / "data").mkdir(parents=True)
        sh(["git", "init", "-q", "-b", "main", "."], self.exp)
        sh(["git", "config", "user.email", "t@example.com"], self.exp)
        sh(["git", "config", "user.name", "Test"], self.exp)
        (self.exp / "train.py").write_text(TRAIN, encoding="utf-8")
        (self.exp / "data" / "raw.csv").write_text("1\n2\n3\n4\n", encoding="utf-8")
        (self.exp / ".gitignore").write_text("data/\nout/\n.vault-replay/\n", encoding="utf-8")
        sh(["git", "add", "-A"], self.exp)
        sh(["git", "commit", "-q", "-m", "init"], self.exp)
        self.env = {**os.environ, "RESEARCH_VAULT": str(self.base / "vault"),
                    "RESEARCH_VAULT_PROJECT": "demo", "PYTHONHASHSEED": "0"}
        self.env.pop("RMS_ROOT", None)
        self.env.pop("DRIFT", None)

    def tearDown(self):
        self.tmp.cleanup()

    def vault(self, *args, check=True, cwd=None):
        return sh([sys.executable, str(VAULT), *args], cwd or self.exp, self.env, check)

    def run_experiment(self, node="H-001", *extra):
        p = self.vault("run", "--node", node, "--data", "data", "--outputs", "out",
                       "--metrics", "out/metrics.json", "--metric", "score", "--seed", "seed=7",
                       "--no-link", *extra, "--", sys.executable, "train.py", "--seed", "7")
        return p.stdout.split("Capsule ", 1)[1].split(":", 1)[0]

    def manifest(self, ref):
        return json.loads(self.vault("show", ref, "--json").stdout)


class TestCapture(VaultTestCase):
    def test_capsule_pins_code_data_environment_and_outputs(self):
        ref = self.run_experiment()
        m = self.manifest(ref)
        head = sh(["git", "rev-parse", "HEAD"], self.exp).stdout.strip()
        self.assertEqual(m["format"], vault.FORMAT)
        self.assertEqual(m["code"][0]["commit"], head)
        self.assertTrue(m["code"][0]["exact"], "the archive's git tree hash should equal the commit's tree")
        self.assertEqual([d["path"] for d in m["data"]], ["data/raw.csv"])
        self.assertEqual(sorted(o["path"] for o in m["outputs"]), ["out/metrics.json", "out/pred.txt"])
        self.assertEqual(m["run"]["seeds"], {"seed": "7"})
        self.assertEqual(m["run"]["env"]["PYTHONHASHSEED"], "0")
        self.assertEqual(m["run"]["metrics_path"], "out/metrics.json")
        self.assertIn("lock", m["environment"])
        self.assertEqual(m["result"]["metric"], "score")
        self.assertEqual(m["result"]["value"], m["metrics"]["score"])

    def test_manifest_matches_the_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        schema = json.loads((VAULT.parents[1] / "schemas" / "capsule.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(self.manifest(self.run_experiment()), schema)

    def test_capsule_id_carries_the_manifest_hash(self):
        ref = self.run_experiment()
        node, cid = ref.split("/")
        path = self.base / "vault" / "capsules" / "demo" / node / f"{cid}.json"
        import hashlib
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest()[:12], cid.rsplit("-", 1)[1])

    def test_blobs_are_stored_once(self):
        self.run_experiment("H-001")
        before = set(os.listdir(self.base / "vault" / "blobs" / "sha256"))
        self.run_experiment("H-002")
        after = set(os.listdir(self.base / "vault" / "blobs" / "sha256"))
        # Same code, data, lock and outputs: only the console output can differ (it does not here).
        self.assertLessEqual(len(after - before), 2)

    def test_uncommitted_changes_are_refused_unless_allowed(self):
        with open(self.exp / "train.py", "a", encoding="utf-8") as f:
            f.write("# changed\n")
        p = self.vault("run", "--node", "H-001", "--no-link", "--", sys.executable, "train.py", "--seed", "1",
                       check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("uncommitted changes", p.stderr)
        ref = self.run_experiment("H-001", "--allow-dirty")
        m = self.manifest(ref)
        self.assertTrue(m["code"][0]["dirty"])
        self.assertIn("patch", m["code"][0])

    def test_secret_environment_variables_are_not_recorded(self):
        self.env["API_TOKEN"] = "x"
        p = self.vault("run", "--node", "H-001", "--env", "API_TOKEN", "--no-link", "--",
                       sys.executable, "train.py", "--seed", "1", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("looks like a secret", p.stderr)

    def test_data_outside_the_repository_is_refused(self):
        outside = self.base / "elsewhere.csv"
        outside.write_text("1\n", encoding="utf-8")
        p = self.vault("run", "--node", "H-001", "--data", str(outside), "--no-link", "--",
                       sys.executable, "train.py", "--seed", "1", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("outside", p.stderr)

    def test_capture_records_a_run_that_already_happened(self):
        sh([sys.executable, "train.py", "--seed", "7"], self.exp, self.env)
        p = self.vault("capture", "--node", "H-001", "--cmd", f"{sys.executable} train.py --seed 7",
                       "--data", "data", "--outputs", "out", "--metrics", "out/metrics.json", "--no-link")
        ref = p.stdout.split("Capsule ", 1)[1].split(":", 1)[0]
        m = self.manifest(ref)
        self.assertFalse(m["run"]["observed"])
        self.assertEqual(m["run"]["argv"][1:], ["train.py", "--seed", "7"])


class TestVerifyRestoreReplay(VaultTestCase):
    def test_verify_detects_a_corrupt_blob(self):
        ref = self.run_experiment()
        self.assertEqual(self.vault("verify", ref, "--deep").returncode, 0)
        m = self.manifest(ref)
        blob = self.base / "vault" / "blobs" / "sha256" / m["data"][0]["sha256"]
        os.chmod(blob, stat.S_IWUSR | stat.S_IRUSR)
        blob.write_text("tampered\n", encoding="utf-8")
        p = self.vault("verify", ref, "--deep", check=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("corrupt", p.stdout)

    def test_verify_checks_the_hash_the_dag_records(self):
        ref = self.run_experiment()
        p = self.vault("verify", ref, "--sha256", "0" * 64, check=False)
        self.assertEqual(p.returncode, 1)

    def test_a_dag_file_in_the_repository_does_not_make_it_dirty(self):
        ws = self.exp
        (ws / "research").mkdir()
        (ws / "research.yaml").write_text('dag_path: "research/hypothesis-dag.yaml"\n'
                                          'node_index_path: "research/node-index.yaml"\n'
                                          'work_items_path: "work/"\n', encoding="utf-8")
        (ws / "research" / "hypothesis-dag.yaml").write_text(
            "nodes:\n- id: H-001\n  hypothesis: Seeds matter\n  status: in_progress\n  parent: null\n",
            encoding="utf-8")
        sh(["git", "add", "-A"], ws)
        sh(["git", "commit", "-q", "-m", "dag in the repository"], ws)
        self.env["RESEARCH_DAG_BIN"] = str(DAG_BIN)
        for seed in ("1", "2"):
            p = self.vault("run", "--node", "H-001", "--outputs", "out", "--metrics", "out/metrics.json",
                           "--", sys.executable, "train.py", "--seed", seed)
            self.assertIn("Recorded on H-001", p.stdout)
        import yaml
        dag = yaml.safe_load((ws / "research" / "hypothesis-dag.yaml").read_text(encoding="utf-8"))
        self.assertEqual(len(dag["nodes"][0]["capsules"]), 2)
        m = self.manifest(f"H-001/{dag['nodes'][0]['capsules'][1]['id']}")
        self.assertFalse(m["code"][0]["dirty"])

    def test_manifests_are_never_overwritten(self):
        backend = vault.LocalBackend(self.base / "vault")
        self.assertTrue(backend.write_once("x/y.json", b"one"))
        self.assertFalse(backend.write_once("x/y.json", b"two"))
        self.assertEqual(backend.read("x/y.json"), b"one")

    def test_restore_materialises_code_data_and_scripts(self):
        ref = self.run_experiment()
        dest = self.base / "restored"
        self.vault("restore", ref, "--to", str(dest))
        self.assertEqual((dest / "repos" / "exp" / "train.py").read_text(encoding="utf-8"), TRAIN)
        self.assertEqual((dest / "repos" / "exp" / "data" / "raw.csv").read_text(encoding="utf-8"), "1\n2\n3\n4\n")
        self.assertTrue((dest / "env" / "requirements.lock").is_file())
        self.assertTrue((dest / "original-outputs" / "out" / "metrics.json").is_file())
        self.assertTrue((dest / "replay.sh").is_file() and (dest / "replay.ps1").is_file())

    def test_replay_reproduces_and_records_a_retest(self):
        ref = self.run_experiment()
        p = self.vault("replay", ref, "--setup", "none", "--to", str(self.base / "r1"), "--no-link")
        self.assertIn("Verdict: identical", p.stdout)
        listing = self.vault("list", "--node", "H-001", "--long").stdout
        self.assertIn("retest", listing)
        self.assertIn("identical", listing)

    def test_replay_reports_drift(self):
        ref = self.run_experiment()
        self.env["DRIFT"] = "1"
        p = self.vault("replay", ref, "--setup", "none", "--to", str(self.base / "r2"), "--no-record", check=False)
        self.assertEqual(p.returncode, 3)
        self.assertIn("Verdict: drifted", p.stdout)

    def test_retest_of_compares_a_new_run_with_an_old_capsule(self):
        ref = self.run_experiment()
        new = self.run_experiment("H-001", "--retest-of", ref)
        m = self.manifest(new)
        self.assertEqual(m["kind"], "retest")
        self.assertEqual(m["retest_of"], ref)
        self.assertEqual(m["comparison"]["verdict"], "identical")


class TestComparison(unittest.TestCase):
    def test_tolerances(self):
        original = {"metrics": {"a": 1.0, "b": {"c": 2.0}, "label": "x"},
                    "outputs": [{"path": "o", "sha256": "1"}]}
        same = vault.compare(original, {"a": 1.0, "b": {"c": 2.0}, "label": "x"}, [{"path": "o", "sha256": "1"}], 0, 0, 0)
        self.assertEqual(same["verdict"], "identical")
        close = vault.compare(original, {"a": 1.0 + 1e-10, "b": {"c": 2.0}, "label": "x"},
                              [{"path": "o", "sha256": "2"}], 0, 1e-9, 0)
        self.assertEqual(close["verdict"], "reproduced")
        far = vault.compare(original, {"a": 1.1, "b": {"c": 2.0}, "label": "x"}, [], 0, 1e-9, 0)
        self.assertEqual(far["verdict"], "drifted")
        self.assertEqual(vault.compare(original, None, [], 1, 0, 0)["verdict"], "failed")

    def test_git_tree_hash_matches_git(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            sh(["git", "init", "-q", "."], d)
            (d / "a").mkdir()
            (d / "a" / "x.txt").write_text("hello\n", encoding="utf-8")
            (d / "run.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(d / "run.sh", 0o755)
            sh(["git", "add", "-A"], d)
            tree = sh(["git", "write-tree"], d).stdout.strip()
            tar = d / "t.tar"
            sh(["git", "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-q", "-m", "x"], d)
            with open(tar, "wb") as f:
                subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=d, stdout=f, check=True)
            self.assertEqual(vault.tar_tree_hash(tar, {}, "sha1"), tree)


class TestDagLink(VaultTestCase):
    def test_capsule_is_appended_to_the_node(self):
        ws = self.exp
        (ws / "research").mkdir()
        (ws / "research.yaml").write_text('dag_path: "research/hypothesis-dag.yaml"\n'
                                          'node_index_path: "research/node-index.yaml"\n'
                                          'work_items_path: "work/"\n', encoding="utf-8")
        (ws / "research" / "hypothesis-dag.yaml").write_text(
            "nodes:\n- id: H-001\n  hypothesis: Seeds matter\n  status: in_progress\n  parent: null\n  target: 0.5\n",
            encoding="utf-8")
        with open(ws / ".gitignore", "a", encoding="utf-8") as f:
            f.write("research/\nresearch.yaml\n")
        sh(["git", "commit", "-q", "-am", "ignore research"], ws)
        self.env["RESEARCH_DAG_BIN"] = str(DAG_BIN)
        p = self.vault("run", "--node", "H-001", "--data", "data", "--outputs", "out", "--metrics", "out/metrics.json",
                       "--metric", "score", "--", sys.executable, "train.py", "--seed", "7")
        self.assertIn("Recorded on H-001", p.stdout)
        import yaml
        dag = yaml.safe_load((ws / "research" / "hypothesis-dag.yaml").read_text(encoding="utf-8"))
        caps = dag["nodes"][0]["capsules"]
        self.assertEqual(len(caps), 1)
        self.assertEqual(caps[0]["kind"], "run")
        self.assertEqual(caps[0]["result"]["target"], 0.5)
        m = self.manifest(f"H-001/{caps[0]['id']}")
        self.assertEqual(m["node"]["snapshot"]["hypothesis"], "Seeds matter")
        self.assertEqual(self.vault("verify", f"H-001/{caps[0]['id']}", "--sha256", caps[0]["sha256"]).returncode, 0)
        sh([sys.executable, str(DAG_BIN / "dag_update.py"), "--action", "update", "--node-id", "H-001",
            "--status", "validated"], ws, self.env)
        sh([sys.executable, str(DAG_BIN / "dag_update.py"), "--action", "add", "--parent", "H-001",
            "--hypothesis", "Child", "--target", "0.1"], ws, self.env)
        sh([sys.executable, str(DAG_BIN / "dag_update.py"), "--action", "update", "--node-id", "H-002",
            "--status", "ineffective"], ws, self.env)
        p = self.vault("coverage", "--verify", "--strict", check=False)
        self.assertIn("1 of 2 result nodes have a capsule", p.stdout)
        self.assertIn("no capsule: H-002", p.stdout)
        self.assertIn("every recorded capsule is intact", p.stdout)
        self.assertEqual(p.returncode, 1)


@unittest.skipIf(os.name == "nt", "the fake gcloud is a POSIX script")
class TestGcsBackend(VaultTestCase):
    def setUp(self):
        super().setUp()
        bindir = self.base / "fakebin"
        bindir.mkdir()
        fake = bindir / "gcloud"
        fake.write_text(f"#!{sys.executable}\n" + FAKE_GCLOUD.split("\n", 1)[1], encoding="utf-8")
        os.chmod(fake, 0o755)
        (self.base / "gcs" / "bucket").mkdir(parents=True)
        self.env["FAKE_GCS"] = str(self.base / "gcs")
        self.env["PATH"] = f"{bindir}{os.pathsep}{self.env['PATH']}"
        self.env["RESEARCH_VAULT"] = "gs://bucket/vault"

    def test_round_trip_through_gcs(self):
        self.vault("init")
        self.assertTrue((self.base / "gcs" / "bucket" / "vault" / "VAULT.md").is_file())
        ref = self.run_experiment()
        self.assertEqual(self.vault("verify", "--all", "--deep").returncode, 0)
        p = self.vault("replay", ref, "--setup", "none", "--to", str(self.base / "r"), "--no-link")
        self.assertIn("Verdict: identical", p.stdout)
        self.assertIn("0 new to the vault", p.stdout)


if __name__ == "__main__":
    unittest.main()
