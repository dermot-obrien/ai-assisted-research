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
import re
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
    override = os.environ.get("CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE")
    if override:
        import json
        with open(ROOT / "auth.log", "a") as log:
            log.write(f"{override} {json.load(open(override))['client_email']} "
                      f"{'leaked' if 'RESEARCH_VAULT_GCP_KEY' in os.environ else 'clean'} "
                      f"{'token' if 'CLOUDSDK_AUTH_ACCESS_TOKEN' in os.environ else 'notoken'}\\n")
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


SCHEMA = json.loads((VAULT.parents[1] / "schemas" / "capsule.schema.json").read_text(encoding="utf-8"))


def validate_schema(case, manifest):
    """Every manifest a test reads must match the published schema (CI installs jsonschema)."""
    try:
        import jsonschema
    except ImportError:
        if os.environ.get("CI"):
            case.fail("jsonschema is not installed, so manifests are not being checked against the schema")
        return
    jsonschema.validate(manifest, SCHEMA)


def force_rmtree(path):
    """shutil.rmtree that also removes read-only files, as git writes its objects on Windows."""
    import shutil

    def writable(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=writable)
    else:
        shutil.rmtree(path, onerror=writable)


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
        m = json.loads(self.vault("show", ref, "--json").stdout)
        validate_schema(self, m)
        return m


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

    def test_outputs_left_by_an_earlier_run_are_not_kept(self):
        (self.exp / "out").mkdir()
        stale = self.exp / "out" / "old-result.txt"
        stale.write_text("from yesterday\n", encoding="utf-8")
        os.utime(stale, (1_000_000_000, 1_000_000_000))
        p = self.vault("run", "--node", "H-001", "--data", "data", "--outputs", "out", "--metrics", "out/metrics.json",
                       "--no-link", "--", sys.executable, "train.py", "--seed", "7")
        self.assertIn("were not written by this run", p.stderr)
        ref = p.stdout.split("Capsule ", 1)[1].split(":", 1)[0]
        self.assertEqual(sorted(o["path"] for o in self.manifest(ref)["outputs"]), ["out/metrics.json", "out/pred.txt"])

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


class TestFixes(VaultTestCase):
    def test_retest_of_exits_3_when_the_result_drifts(self):
        ref = self.run_experiment()
        self.env["DRIFT"] = "1"
        p = self.vault("run", "--node", "H-001", "--data", "data", "--outputs", "out", "--metrics", "out/metrics.json",
                       "--no-link", "--retest-of", ref, "--", sys.executable, "train.py", "--seed", "7", check=False)
        self.assertEqual(p.returncode, 3)
        self.assertIn("Verdict: drifted", p.stdout)

    def test_a_malformed_id_is_named_as_such(self):
        p = self.vault("show", "nonsense", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("is not a capsule id", p.stderr)

    def test_pip_without_a_venv_is_refused_before_restoring(self):
        ref = self.run_experiment()
        dest = self.base / "never"
        p = self.vault("replay", ref, "--setup", "none", "--pip", "six==1.16.0", "--to", str(dest), check=False)
        self.assertEqual(p.returncode, 2)
        self.assertFalse(dest.exists())

    def test_a_second_replay_takes_a_fresh_folder(self):
        ref = self.run_experiment()
        for _ in range(2):
            self.vault("replay", ref, "--setup", "none", "--no-record")
        cid = ref.split("/")[1]
        self.assertTrue((self.exp / ".vault-replay" / f"{cid}-2").is_dir())


class TestCodeBundles(VaultTestCase):
    def commit(self, text, msg):
        with open(self.exp / "train.py", "a", encoding="utf-8") as f:
            f.write(f"# {text}\n")
        sh(["git", "commit", "-q", "-am", msg], self.exp)
        return sh(["git", "rev-parse", "HEAD"], self.exp).stdout.strip()

    def bundles(self):
        return sorted((self.base / "vault" / "repos").rglob("*.bundle"))

    def test_code_is_kept_as_tagged_incremental_bundles(self):
        first = self.manifest(self.run_experiment())["code"][0]
        self.assertEqual(first["storage"], "bundle")
        self.assertEqual(len(first["bundles"]), 1)
        self.assertNotIn("archive", first)
        tag = sh(["git", "rev-parse", f"refs/tags/{first['tag']}"], self.exp).stdout.strip()
        self.assertEqual(tag, first["commit"])
        # The same commit again adds no bundle.
        self.run_experiment()
        self.assertEqual(len(self.bundles()), 1)
        # A new commit adds a bundle of just that commit.
        self.commit("change", "second")
        second = self.manifest(self.run_experiment())["code"][0]
        self.assertEqual(len(second["bundles"]), 2)
        self.assertEqual(len(self.bundles()), 2)
        newest = self.base / "vault" / "repos" / second["root"] / f"{second['commit']}.bundle"
        oldest = self.base / "vault" / "repos" / second["root"] / f"{first['commit']}.bundle"
        prereq = sh(["git", "bundle", "list-heads", str(newest)], self.exp).stdout
        self.assertIn(second["tag"], prereq)
        verify = sh(["git", "bundle", "verify", str(newest)], self.exp).stdout + \
            sh(["git", "bundle", "verify", str(newest)], self.exp).stderr
        self.assertIn("requires", verify)
        self.assertLess(newest.stat().st_size, oldest.stat().st_size)

    def test_restore_rebuilds_the_repository_without_the_original(self):
        ref = self.run_experiment()
        m = self.manifest(ref)
        force_rmtree(self.exp)
        dest = self.base / "restored"
        sh([sys.executable, str(VAULT), "restore", ref, "--to", str(dest)], self.base, self.env)
        repo = dest / "repos" / "exp"
        self.assertEqual(sh(["git", "rev-parse", "HEAD"], repo).stdout.strip(), m["code"][0]["commit"])
        self.assertEqual(sh(["git", "rev-parse", "HEAD^{tree}"], repo).stdout.strip(), m["code"][0]["tree"])
        self.assertEqual((repo / "train.py").read_text(encoding="utf-8"), TRAIN)
        self.assertEqual((repo / "data" / "raw.csv").read_text(encoding="utf-8"), "1\n2\n3\n4\n")

    def test_a_split_history_restores_from_every_branch(self):
        self.run_experiment()
        sh(["git", "checkout", "-q", "-b", "side"], self.exp)
        self.commit("side", "side work")
        self.run_experiment()
        sh(["git", "checkout", "-q", "main"], self.exp)
        self.commit("main", "main work")
        ref = self.run_experiment()
        m = self.manifest(ref)
        self.assertEqual(len(m["code"][0]["bundles"]), 3)
        dest = self.base / "restored"
        self.vault("restore", ref, "--to", str(dest))
        self.assertEqual(sh(["git", "rev-parse", "HEAD"], dest / "repos" / "exp").stdout.strip(),
                         m["code"][0]["commit"])
        self.assertEqual(self.vault("verify", ref, "--deep").returncode, 0)

    def test_the_tag_is_pushed_and_keeps_a_deleted_branch(self):
        remote = self.base / "remote.git"
        sh(["git", "init", "-q", "--bare", str(remote)], self.base)
        sh(["git", "remote", "add", "origin", str(remote)], self.exp)
        sh(["git", "push", "-q", "origin", "main"], self.exp)
        sh(["git", "checkout", "-q", "-b", "experiment"], self.exp)
        commit = self.commit("try", "an experiment")
        sh(["git", "push", "-q", "origin", "experiment"], self.exp)
        m = self.manifest(self.run_experiment())
        self.assertTrue(m["code"][0]["tag_pushed"])
        sh(["git", "push", "-q", "origin", "--delete", "experiment"], self.exp)
        tags = sh(["git", "ls-remote", "--tags", str(remote)], self.base).stdout
        self.assertIn(commit, tags)

    def test_a_missing_bundle_fails_verification(self):
        ref = self.run_experiment()
        for b in self.bundles():
            os.chmod(b, stat.S_IWUSR | stat.S_IRUSR)
            b.unlink()
        p = self.vault("verify", ref, check=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("code bundles missing", p.stdout)

    def test_a_shallow_clone_is_kept_as_a_compressed_snapshot(self):
        self.commit("more", "second")
        shallow = self.base / "shallow"
        sh(["git", "clone", "-q", "--depth", "1", self.exp.as_uri(), str(shallow)], self.base)
        (shallow / "data").mkdir()
        (shallow / "data" / "raw.csv").write_text("1\n2\n", encoding="utf-8")
        p = self.vault("run", "--node", "H-001", "--data", "data", "--outputs", "out", "--metrics", "out/metrics.json",
                       "--no-link", "--no-push-tag", "--", sys.executable, "train.py", "--seed", "1", cwd=shallow)
        self.assertIn("shallow clone", p.stderr)
        ref = p.stdout.split("Capsule ", 1)[1].split(":", 1)[0]
        code = self.manifest(ref)["code"][0]
        self.assertEqual((code["storage"], code["archive"]["format"], code["exact"]), ("archive", "tar.gz", True))
        dest = self.base / "restored"
        self.vault("restore", ref, "--to", str(dest))
        self.assertTrue((dest / "repos" / "shallow" / "train.py").is_file())

    def test_archive_storage_on_request_is_deterministic(self):
        a = self.manifest(self.run_experiment("H-001", "--code-storage", "archive"))["code"][0]
        b = self.manifest(self.run_experiment("H-002", "--code-storage", "archive"))["code"][0]
        self.assertEqual(a["archive"]["sha256"], b["archive"]["sha256"])
        self.assertEqual(self.bundles(), [])


class TestCodeEdges(VaultTestCase):
    """The ways code reaches a run besides one clean repository."""

    def git_c(self, *args, cwd):
        return sh(["git", "-c", "protocol.file.allow=always", *args], cwd, self.env)

    def test_submodules_are_captured_and_restored(self):
        lib = self.base / "lib"
        lib.mkdir()
        sh(["git", "init", "-q", "-b", "main", "."], lib)
        (lib / "value.txt").write_text("41\n", encoding="utf-8")
        sh(["git", "add", "-A"], lib)
        sh(["git", "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-q", "-m", "lib"], lib)
        self.git_c("submodule", "add", "-q", str(lib), "vendor/lib", cwd=self.exp)
        (self.exp / "use_lib.py").write_text(
            "import json, os\nv = int(open('vendor/lib/value.txt').read()) + 1\nos.makedirs('out', exist_ok=True)\n"
            "json.dump({'score': v}, open('out/metrics.json', 'w'))\n", encoding="utf-8")
        sh(["git", "add", "-A"], self.exp)
        sh(["git", "commit", "-q", "-m", "use a submodule"], self.exp)
        p = self.vault("run", "--node", "H-001", "--outputs", "out", "--metrics", "out/metrics.json", "--no-link",
                       "--", sys.executable, "use_lib.py")
        ref = p.stdout.split("Capsule ", 1)[1].split(":", 1)[0]
        code = self.manifest(ref)["code"]
        self.assertEqual([c["name"] for c in code], ["exp", "exp--vendor-lib"])
        self.assertEqual(code[1]["path"], "vendor/lib")
        self.assertEqual(code[0]["submodules"]["vendor/lib"], code[1]["commit"])
        dest = self.base / "restored"
        self.vault("restore", ref, "--to", str(dest))
        self.assertEqual((dest / "repos" / "exp" / "vendor" / "lib" / "value.txt").read_text(encoding="utf-8"), "41\n")
        r = self.vault("replay", ref, "--setup", "none", "--to", str(self.base / "r"), "--no-record")
        self.assertIn("Verdict: identical", r.stdout)

    def test_a_submodule_that_is_not_checked_out_is_refused(self):
        lib = self.base / "lib"
        lib.mkdir()
        sh(["git", "init", "-q", "-b", "main", "."], lib)
        (lib / "value.txt").write_text("1\n", encoding="utf-8")
        sh(["git", "add", "-A"], lib)
        sh(["git", "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-q", "-m", "lib"], lib)
        self.git_c("submodule", "add", "-q", str(lib), "vendor/lib", cwd=self.exp)
        sh(["git", "commit", "-q", "-m", "submodule"], self.exp)
        clone = self.base / "clone"
        sh(["git", "clone", "-q", self.exp.as_uri(), str(clone)], self.base)
        (clone / "data").mkdir()
        (clone / "data" / "raw.csv").write_text("1\n", encoding="utf-8")
        p = self.vault("run", "--node", "H-001", "--no-link", "--", sys.executable, "train.py", "--seed", "1",
                       cwd=clone, check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("submodule vendor/lib of clone is not checked out", p.stderr)

    def test_a_second_repository_restores_beside_the_first(self):
        other = self.base / "shared"
        other.mkdir()
        sh(["git", "init", "-q", "-b", "main", "."], other)
        (other / "const.txt").write_text("3\n", encoding="utf-8")
        sh(["git", "add", "-A"], other)
        sh(["git", "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-q", "-m", "shared"], other)
        (self.exp / "use_other.py").write_text(
            "import json, os\nv = int(open('../shared/const.txt').read())\nos.makedirs('out', exist_ok=True)\n"
            "json.dump({'score': v}, open('out/metrics.json', 'w'))\n", encoding="utf-8")
        sh(["git", "add", "-A"], self.exp)
        sh(["git", "commit", "-q", "-m", "use another repository"], self.exp)
        p = self.vault("run", "--node", "H-001", "--repo", str(other), "--outputs", "out", "--metrics",
                       "out/metrics.json", "--no-link", "--", sys.executable, "use_other.py")
        ref = p.stdout.split("Capsule ", 1)[1].split(":", 1)[0]
        code = self.manifest(ref)["code"]
        self.assertEqual((code[1]["name"], code[1]["path"]), ("shared", "../shared"))
        r = self.vault("replay", ref, "--setup", "none", "--to", str(self.base / "r"), "--no-record")
        self.assertIn("Verdict: identical", r.stdout)
        self.assertTrue((self.base / "r" / "repos" / "shared" / "const.txt").is_file())

    def test_a_dirty_capture_restores_the_patch_and_untracked_files(self):
        with open(self.exp / "train.py", "a", encoding="utf-8") as f:
            f.write("# an uncommitted line\n")
        (self.exp / "notes.txt").write_text("untracked\n", encoding="utf-8")
        ref = self.run_experiment("H-001", "--allow-dirty")
        dest = self.base / "restored"
        self.vault("restore", ref, "--to", str(dest))
        restored = dest / "repos" / "exp"
        self.assertTrue((restored / "train.py").read_text(encoding="utf-8").endswith("# an uncommitted line\n"))
        self.assertEqual((restored / "notes.txt").read_text(encoding="utf-8"), "untracked\n")

    def checkout_again(self):
        """Check every tracked file out again, so the working files follow the repository's eol settings."""
        for rel in sh(["git", "ls-files"], self.exp).stdout.split():
            (self.exp / rel).unlink()
        sh(["git", "checkout", "--", "."], self.exp)

    def test_restore_ignores_the_users_line_ending_settings(self):
        sh(["git", "config", "core.autocrlf", "false"], self.exp)
        self.checkout_again()
        ref = self.run_experiment()
        cfg = self.base / "gitconfig"
        cfg.write_text("[core]\n\tautocrlf = true\n", encoding="utf-8")
        self.env["GIT_CONFIG_GLOBAL"] = str(cfg)
        dest = self.base / "restored"
        self.vault("restore", ref, "--to", str(dest))
        self.assertNotIn(b"\r\n", (dest / "repos" / "exp" / "train.py").read_bytes())

    def test_restore_writes_the_line_endings_the_run_read(self):
        """A run on a machine that checks files out with CRLF (Windows) restores with CRLF."""
        sh(["git", "config", "core.autocrlf", "true"], self.exp)
        self.checkout_again()
        self.assertIn(b"\r\n", (self.exp / "train.py").read_bytes())
        ref = self.run_experiment()
        self.assertEqual(self.manifest(ref)["code"][0]["checkout"]["core.autocrlf"], "true")
        dest = self.base / "restored"
        self.vault("restore", ref, "--to", str(dest))
        restored = dest / "repos" / "exp" / "train.py"
        self.assertEqual(restored.read_bytes(), (self.exp / "train.py").read_bytes())

    def test_two_clones_share_one_vault(self):
        self.run_experiment()
        clone = self.base / "clone"
        sh(["git", "clone", "-q", self.exp.as_uri(), str(clone)], self.base)
        sh(["git", "config", "user.email", "c@example.com"], clone)
        sh(["git", "config", "user.name", "Clone"], clone)
        (clone / "data").mkdir()
        (clone / "data" / "raw.csv").write_text("5\n6\n", encoding="utf-8")
        with open(clone / "train.py", "a", encoding="utf-8") as f:
            f.write("# from the clone\n")
        sh(["git", "commit", "-q", "-am", "clone work"], clone)
        with open(self.exp / "train.py", "a", encoding="utf-8") as f:
            f.write("# from the original\n")
        sh(["git", "commit", "-q", "-am", "original work"], self.exp)
        refs = []
        for where in (clone, self.exp):
            p = self.vault("run", "--node", "H-002", "--data", "data", "--outputs", "out", "--metrics",
                           "out/metrics.json", "--no-link", "--no-push-tag", "--",
                           sys.executable, "train.py", "--seed", "3", cwd=where)
            refs.append(p.stdout.split("Capsule ", 1)[1].split(":", 1)[0])
        for ref in refs:
            self.assertEqual(self.vault("verify", ref, "--deep").returncode, 0)
            r = self.vault("replay", ref, "--setup", "none", "--to", str(self.base / ref.replace("/", "_")),
                           "--no-record")
            self.assertIn("Verdict: identical", r.stdout)

    def test_a_tag_name_taken_by_another_commit_falls_back_to_the_full_id(self):
        head = sh(["git", "rev-parse", "HEAD"], self.exp).stdout.strip()
        with open(self.exp / "train.py", "a", encoding="utf-8") as f:
            f.write("# next\n")
        sh(["git", "commit", "-q", "-am", "next"], self.exp)
        new = sh(["git", "rev-parse", "HEAD"], self.exp).stdout.strip()
        sh(["git", "tag", f"vault/{new[:12]}", head], self.exp)
        code = self.manifest(self.run_experiment())["code"][0]
        self.assertEqual(code["tag"], f"vault/{new}")
        self.assertEqual(sh(["git", "rev-parse", f"refs/tags/vault/{new}"], self.exp).stdout.strip(), new)

    def test_an_unreachable_remote_still_keeps_the_capsule(self):
        sh(["git", "remote", "add", "origin", str(self.base / "no-such-remote.git")], self.exp)
        p = self.vault("run", "--node", "H-001", "--data", "data", "--no-link", "--",
                       sys.executable, "train.py", "--seed", "1")
        self.assertIn("could not push tag", p.stderr)
        ref = p.stdout.split("Capsule ", 1)[1].split(":", 1)[0]
        self.assertFalse(self.manifest(ref)["code"][0]["tag_pushed"])
        self.assertEqual(self.vault("verify", ref, "--deep").returncode, 0)


class TestIntegrity(VaultTestCase):
    """Damage to the vault is found, never replayed."""

    def bundle_paths(self):
        return sorted((self.base / "vault" / "repos").rglob("*.bundle"), key=lambda b: b.stat().st_mtime)

    def test_a_corrupt_bundle_is_detected(self):
        ref = self.run_experiment()
        b = self.bundle_paths()[0]
        os.chmod(b, stat.S_IWUSR | stat.S_IRUSR)
        data = bytearray(b.read_bytes())
        data[len(data) // 2] ^= 0xFF
        b.write_bytes(bytes(data))
        p = self.vault("verify", ref, "--deep", check=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("FAIL", p.stdout)
        r = self.vault("restore", ref, "--to", str(self.base / "r"), check=False)
        self.assertNotEqual(r.returncode, 0)

    def test_a_missing_bundle_in_the_chain_is_named(self):
        self.run_experiment()
        with open(self.exp / "train.py", "a", encoding="utf-8") as f:
            f.write("# second\n")
        sh(["git", "commit", "-q", "-am", "second"], self.exp)
        ref = self.run_experiment()
        first = self.bundle_paths()[0]
        os.chmod(first, stat.S_IWUSR | stat.S_IRUSR)
        first.unlink()
        p = self.vault("restore", ref, "--to", str(self.base / "r"), check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("missing from", p.stderr)

    def test_restored_code_whose_tree_differs_from_the_record_is_refused(self):
        ref = self.run_experiment()
        m = self.manifest(ref)
        m["code"][0]["tree"] = "0" * 40
        data = vault.canonical(m)
        import hashlib as _hashlib
        cid = f"{m['created_at'].replace('-', '').replace(':', '')}-{_hashlib.sha256(data).hexdigest()[:12]}"
        (self.base / "vault" / "capsules" / "demo" / "H-001" / f"{cid}.json").write_bytes(data)
        p = self.vault("restore", f"H-001/{cid}", "--to", str(self.base / "r"), check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("not the recorded", p.stderr)

    def test_a_format_1_capsule_still_restores(self):
        """A capsule written by experiment-vault 1.0.0: format 1, code as a plain tar."""
        ref = self.run_experiment("H-001", "--code-storage", "archive")
        m = self.manifest(ref)
        repo = m["code"][0]
        blobs = self.base / "vault" / "blobs" / "sha256"
        import gzip as _gzip
        import hashlib as _hashlib
        tar = _gzip.decompress((blobs / repo["archive"]["sha256"]).read_bytes())
        tar_hex = _hashlib.sha256(tar).hexdigest()
        (blobs / tar_hex).write_bytes(tar)
        repo.pop("storage")
        repo["archive"] = {"sha256": tar_hex, "size": len(tar), "format": "tar"}
        m["format"] = "experiment-vault/1"
        data = vault.canonical(m)
        cid = f"{m['created_at'].replace('-', '').replace(':', '')}-{_hashlib.sha256(data).hexdigest()[:12]}"
        (self.base / "vault" / "capsules" / "demo" / "H-001" / f"{cid}.json").write_bytes(data)
        r = self.vault("replay", f"H-001/{cid}", "--setup", "none", "--to", str(self.base / "r"), "--no-record")
        self.assertIn("Verdict: identical", r.stdout)

    def test_a_newer_format_is_refused(self):
        ref = self.run_experiment()
        m = self.manifest(ref)
        m["format"] = "experiment-vault/99"
        data = vault.canonical(m)
        import hashlib as _hashlib
        cid = f"{m['created_at'].replace('-', '').replace(':', '')}-{_hashlib.sha256(data).hexdigest()[:12]}"
        (self.base / "vault" / "capsules" / "demo" / "H-001" / f"{cid}.json").write_bytes(data)
        p = self.vault("show", f"H-001/{cid}", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("cannot read; update the skill", p.stderr)

    def test_the_vault_never_replaces_a_stored_file(self):
        backend = vault.LocalBackend(self.base / "vault")
        one, two = self.base / "one", self.base / "two"
        one.write_text("one", encoding="utf-8")
        two.write_text("two", encoding="utf-8")
        self.assertEqual(backend.put_files({"repos/r/x.bundle": one}), 1)
        self.assertEqual(backend.put_files({"repos/r/x.bundle": two}), 0)
        self.assertEqual(backend.read("repos/r/x.bundle"), b"one")


class TestPreflight(VaultTestCase):
    """--dry-run checks everything and changes nothing."""

    def snapshot(self):
        vault_files = sorted(str(p) for p in (self.base / "vault").rglob("*")) if (self.base / "vault").exists() else []
        tags = sh(["git", "tag"], self.exp).stdout
        return vault_files, tags

    def test_a_ready_capture_changes_nothing(self):
        self.vault("init")
        before = self.snapshot()
        p = self.vault("run", "--node", "H-001", "--data", "data", "--outputs", "out", "--metrics", "out/metrics.json",
                       "--dry-run", "--", sys.executable, "train.py", "--seed", "1")
        self.assertIn("ready: nothing was run, tagged or uploaded", p.stdout)
        self.assertIn("as bundle", p.stdout)
        self.assertIn("data: 1 files", p.stdout)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.exp / "out").exists(), "the command must not run")

    def test_every_problem_is_named(self):
        with open(self.exp / "train.py", "a", encoding="utf-8") as f:
            f.write("# dirty\n")
        self.env["API_SECRET"] = "x"
        p = self.vault("run", "--node", "bad id!", "--data", "../elsewhere", "--outputs", "../out", "--env",
                       "API_SECRET", "--dry-run", "--", sys.executable, "train.py", check=False)
        self.assertEqual(p.returncode, 2)
        for expected in ("not initialised", "node id", "uncommitted changes", "data ../elsewhere does not exist",
                         "output ../out is outside", "looks like a secret"):
            self.assertIn(expected, p.stdout)


class TestGuarantees(unittest.TestCase):
    """references/guarantees.md names the tests that prove each guarantee; they must exist."""

    def test_every_guarantee_names_tests_that_exist(self):
        page = (VAULT.parents[1] / "references" / "guarantees.md").read_text(encoding="utf-8")
        rows = [line for line in page.splitlines() if re.match(r"^\| G\d+ \|", line)]
        self.assertGreaterEqual(len(rows), 20)
        sources = "".join((REPO / "tests" / f).read_text(encoding="utf-8")
                          for f in ("test_experiment_vault.py", "test_dag_store.py", "test_datasets.py"))
        ci = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        ids = []
        for row in rows:
            gid, _, proof = [c.strip() for c in row.strip("|").split("|")]
            ids.append(gid)
            named = re.findall(r"`(test_\w+)`", proof)
            step = re.search(r"ci: (.+)$", proof)
            self.assertTrue(named or step, f"{gid} names no test")
            for t in named:
                self.assertIn(f"def {t}(", sources, f"{gid} names {t}, which does not exist")
            if step:
                self.assertIn(f"name: {step.group(1).strip()}", ci, f"{gid} names a CI step that does not exist")
        self.assertEqual(ids, [f"G{i}" for i in range(1, len(ids) + 1)], "guarantee ids must run G1, G2, ...")


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
            sh(["git", "config", "core.autocrlf", "false"], d)
            (d / "a" / "x.txt").write_text("hello\n", encoding="utf-8", newline="\n")
            (d / "run.sh").write_text("#!/bin/sh\n", encoding="utf-8", newline="\n")
            os.chmod(d / "run.sh", 0o755)
            sh(["git", "add", "-A"], d)
            tree = sh(["git", "write-tree"], d).stdout.strip()
            tar = d / "t.tar"
            sh(["git", "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-q", "-m", "x"], d)
            with open(tar, "wb") as f:
                subprocess.run(["git", "-c", "core.autocrlf=false", "archive", "--format=tar", "HEAD"], cwd=d,
                               stdout=f, check=True)
            self.assertEqual(vault.tar_tree_hash(tar, {}, "sha1"), tree)


class TestDagLink(VaultTestCase):
    def test_capsule_is_appended_to_the_node(self):
        ws = self.exp
        (ws / "research").mkdir()
        (ws / "research.yaml").write_text('dag_path: "research/hypothesis-dag.yaml"\n'
                                          'node_index_path: "research/node-index.yaml"\n'
                                          'work_items_path: "work/"\n', encoding="utf-8")
        (ws / "research" / "hypothesis-dag.yaml").write_text(
            "nodes:\n- id: H-001\n  hypothesis: Seeds matter\n  status: in_progress\n  parent: null\n  target_improvement: 0.5\n",
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

    FAKE_KEY = {"type": "service_account", "client_email": "research-agents@p.iam.gserviceaccount.com",
                "private_key": "-----BEGIN PRIVATE KEY-----\nNOT-A-REAL-KEY\n-----END PRIVATE KEY-----\n"}

    def test_a_key_in_the_environment_authenticates_only_the_vaults_gcloud_calls(self):
        self.env["RESEARCH_VAULT_GCP_KEY"] = json.dumps(self.FAKE_KEY)
        (self.exp / "leak.py").write_text(
            "import json, os\nos.makedirs('out', exist_ok=True)\n"
            "json.dump({'score': 1, 'saw_key': 'RESEARCH_VAULT_GCP_KEY' in os.environ}, open('out/metrics.json', 'w'))\n",
            encoding="utf-8")
        sh(["git", "add", "-A"], self.exp)
        sh(["git", "commit", "-q", "-m", "leak check"], self.exp)
        self.vault("init")
        p = self.vault("run", "--node", "H-001", "--outputs", "out", "--metrics", "out/metrics.json", "--no-link",
                       "--", sys.executable, "leak.py")
        ref = p.stdout.split("Capsule ", 1)[1].split(":", 1)[0]
        log = (self.base / "gcs" / "auth.log").read_text(encoding="utf-8").splitlines()
        self.assertTrue(log, "gcloud was never given the key")
        paths = {line.split()[0] for line in log}
        self.assertEqual({line.split()[1] for line in log}, {self.FAKE_KEY["client_email"]})
        self.assertEqual({line.split()[2] for line in log}, {"clean"}, "gcloud's environment kept the key variable")
        for path in paths:
            self.assertFalse(os.path.exists(path), "the key file outlived the run")
        m = self.manifest(ref)
        self.assertFalse(m["metrics"]["saw_key"], "the experiment was given the vault's key")
        self.assertNotIn("NOT-A-REAL-KEY", json.dumps(m))
        self.assertNotIn("RESEARCH_VAULT_GCP_KEY", json.dumps(m))

    def test_a_key_given_as_one_line_json_or_base64_is_used(self):
        import base64
        pretty = json.dumps(self.FAKE_KEY, indent=2)
        for value in (json.dumps(self.FAKE_KEY), base64.b64encode(pretty.encode()).decode()):
            log = self.base / "gcs" / "auth.log"
            if log.exists():
                log.unlink()
            self.env["RESEARCH_VAULT_GCP_KEY"] = value
            self.vault("init")
            self.assertIn(self.FAKE_KEY["client_email"], log.read_text(encoding="utf-8"))

    def test_a_preset_access_token_does_not_override_the_key(self):
        """A cloud session presets CLOUDSDK_AUTH_ACCESS_TOKEN for its proxy; gcloud prefers it to a key file."""
        self.env["CLOUDSDK_AUTH_ACCESS_TOKEN"] = "placeholder-14"
        self.env["RESEARCH_VAULT_GCP_KEY"] = json.dumps(self.FAKE_KEY)
        self.vault("init")
        log = (self.base / "gcs" / "auth.log").read_text(encoding="utf-8").splitlines()
        self.assertTrue(log)
        self.assertEqual({line.split()[3] for line in log}, {"notoken"},
                         "gcloud was given the preset access token, which it would use instead of the key")

    def test_a_malformed_key_is_named_without_printing_it(self):
        self.env["RESEARCH_VAULT_GCP_KEY"] = "secret-but-not-json"
        p = self.vault("init", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("RESEARCH_VAULT_GCP_KEY is neither JSON nor base64 JSON", p.stderr)
        self.assertNotIn("secret-but-not-json", p.stdout + p.stderr)
        self.env["RESEARCH_VAULT_GCP_KEY"] = "{not json"
        p = self.vault("init", check=False)
        self.assertIn("RESEARCH_VAULT_GCP_KEY is not JSON", p.stderr)
        self.env["RESEARCH_VAULT_GCP_KEY"] = json.dumps({"type": "authorized_user"})
        p = self.vault("init", check=False)
        self.assertIn("is not a service account key", p.stderr)

    def test_without_a_key_gcloud_uses_the_signed_in_account(self):
        self.vault("init")
        self.assertFalse((self.base / "gcs" / "auth.log").exists())

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
