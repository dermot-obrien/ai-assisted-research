# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""
Tests for runtimes: the machine type, Python build, locked environment and determinism settings a node's
evidence runs must match, so the same experiment gives the same result on any machine and agent platform.
They need uv (CI installs it) and skip without it. Run from the repository root:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_experiment_vault as tev  # noqa: E402

EXPERIMENT = textwrap.dedent("""\
    import json, os, re
    # Stands in for a library whose new version changes the result: the factor comes with the project files.
    found = re.search(r"factor = (\\d+)", open("pyproject.toml").read())
    factor = int(found.group(1)) if found else 1
    os.makedirs("out", exist_ok=True)
    json.dump({"score": 0.25 * factor, "threads": os.environ.get("OMP_NUM_THREADS"),
               "hashseed": os.environ.get("PYTHONHASHSEED")}, open("out/metrics.json", "w"))
    open("out/pred.txt", "w").write(f"{0.25 * factor}\\n")
    """)

PYPROJECT = textwrap.dedent("""\
    [project]
    name = "exp"
    version = "0"
    requires-python = ">=3.10"
    dependencies = []
    """)


@unittest.skipUnless(shutil.which("uv"), "uv is not installed")
class RuntimeTestCase(tev.VaultTestCase):
    def setUp(self):
        super().setUp()
        for k in [k for k in self.env if k.startswith("UV_NATIVE_TLS")]:
            self.env.pop(k)
        self.env.pop("OMP_NUM_THREADS", None)
        (self.exp / "evaluate.py").write_text(EXPERIMENT, encoding="utf-8", newline="\n")
        (self.exp / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8", newline="\n")
        with open(self.exp / ".gitignore", "a", encoding="utf-8") as f:
            f.write(".venv/\nresearch/\nresearch.yaml\n")
        tev.sh(["uv", "lock", "--offline", "-q"], self.exp, self.env)
        tev.sh(["uv", "sync", "--offline", "-q", "--python", sys.executable], self.exp, self.env)
        tev.sh(["git", "add", "-A"], self.exp)
        tev.sh(["git", "commit", "-q", "-m", "uv project"], self.exp)
        self.py = str(self.exp / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
        (self.exp / "research").mkdir()
        (self.exp / "research.yaml").write_text("dag_path: research/dag.yaml\nnode_index_path: research/index.yaml\n"
                                                "work_items_path: work/\n", encoding="utf-8")
        self.dag("rt")
        self.env["RESEARCH_DAG_BIN"] = str(tev.DAG_BIN)
        self.vault("init")

    def dag(self, runtime):
        (self.exp / "research" / "dag.yaml").write_text(
            "nodes:\n- id: H-1\n  hypothesis: Seeds matter\n  status: framed\n  parent: null\n"
            + (f"  runtime: {runtime}\n" if runtime else ""), encoding="utf-8")

    def define(self, name="rt", profile="none", *extra):
        return self.vault("runtime", "create", name, "--python", self.py, "--profile", profile, *extra)

    def evaluate(self, *extra, python=None, check=True):
        py = python or self.py
        p = self.vault("run", "--node", "H-1", "--python", py, "--outputs", "out", "--metrics", "out/metrics.json",
                       "--metric", "score", *extra, "--", py, "evaluate.py", check=check)
        if not check:
            return p
        return p.stdout.split("Capsule ", 1)[1].split(":", 1)[0]

    def runtime_file(self, name):
        return self.base / "vault" / "runtimes" / f"{name}.json"

    def foreign(self, name, **change):
        """A runtime defined on another kind of machine: this one's record with fields changed."""
        record = json.loads(self.runtime_file("rt").read_text(encoding="utf-8"))
        record.update(name=name, **change)
        self.runtime_file(name).write_text(json.dumps(record, sort_keys=True, indent=2), encoding="utf-8")


class TestRuntimes(RuntimeTestCase):
    def test_a_runtime_is_defined_once(self):
        p = self.define()
        self.assertIn("Defined runtime rt", p.stdout)
        record = json.loads(self.runtime_file("rt").read_text(encoding="utf-8"))
        self.assertEqual(record["python"]["version"], json.loads(tev.sh(
            [self.py, "-c", "import json, platform; print(json.dumps(platform.python_version()))"], self.exp).stdout))
        self.assertEqual((record["tolerance"], record["parity"], record["lock"]), ({"rtol": 0.0, "atol": 0.0}, True, "uv"))
        p = self.vault("runtime", "create", "rt", "--python", self.py, check=False)
        self.assertIn("a runtime is defined once", p.stderr)
        self.assertEqual(self.vault("runtime", "check", "rt", "--python", self.py).returncode, 0)

    def test_an_evidence_run_must_match_the_nodes_runtime(self):
        self.define()
        p = self.evaluate(python=sys.executable, check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("is not the project's environment", p.stderr)
        self.foreign("arm", arch="linux-aarch64")
        self.dag("arm")
        p = self.evaluate(check=False)
        self.assertIn("runtime arm is linux-aarch64", p.stderr)
        self.foreign("py39", python={"version": "3.9.0", "build": "3.9.0 (other build)", "implementation": "CPython",
                                     "managed": True})
        self.dag("py39")
        p = self.evaluate(check=False)
        self.assertIn("runtime py39 is 3.9.0", p.stderr)
        self.assertIn("uv python install 3.9.0", p.stderr)
        self.assertFalse((self.base / "vault" / "capsules" / "demo" / "H-1").exists())

    def test_an_environment_that_drifts_from_its_lock_is_refused(self):
        self.define()
        site = tev.sh([self.py, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], self.exp).stdout.strip()
        extra = Path(site) / "stray-1.0.dist-info"
        extra.mkdir()
        (extra / "METADATA").write_text("Metadata-Version: 2.1\nName: stray\nVersion: 1.0\n", encoding="utf-8")
        (extra / "RECORD").write_text("", encoding="utf-8")
        (extra / "INSTALLER").write_text("pip\n", encoding="utf-8")
        p = self.evaluate(check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("does not match uv.lock", p.stderr)

    def test_an_exploratory_run_is_kept_with_what_differed(self):
        self.define()
        ref = self.evaluate("--exploratory", python=sys.executable)
        m = self.manifest(ref)
        self.assertFalse(m["runtime"]["match"])
        self.assertTrue(m["runtime"]["problems"])
        self.assertEqual(m["evidence"]["class"], "exploratory")

    def test_the_runtime_sets_the_settings_and_the_tolerance(self):
        self.define("rt", "none", "--rtol", "1e-12")
        self.vault("runtime", "create", "det", "--python", self.py, "--profile", "cpu-deterministic-v1")
        self.env["OMP_NUM_THREADS"] = "8"
        if sys.platform == "linux":
            self.dag("det")
            m = self.manifest(self.evaluate("--rtol", "0.5"))
            self.assertEqual((m["metrics"]["threads"], m["metrics"]["hashseed"]), ("1", "0"),
                             "the profile overrides what the caller set")
            self.assertEqual(m["run"]["env"]["OMP_NUM_THREADS"], "1")
            self.assertEqual(m["tolerance"], {"rtol": 0.0, "atol": 0.0}, "the runtime fixes the tolerance")
        self.dag("rt")
        m = self.manifest(self.evaluate())
        self.assertEqual(m["metrics"]["threads"], "8", "profile none changes nothing")
        self.assertEqual(m["tolerance"], {"rtol": 1e-12, "atol": 0.0})

    def test_a_capture_cannot_be_evidence_for_a_runtime(self):
        self.define()
        tev.sh([self.py, "evaluate.py"], self.exp, self.env)
        p = self.vault("capture", "--node", "H-1", "--python", self.py, "--cmd", f"{self.py} evaluate.py",
                       "--outputs", "out", "--metrics", "out/metrics.json", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("a capture cannot show the machine a past run ran on", p.stderr)

    def test_the_node_and_capsule_record_where_it_ran(self):
        self.define()
        self.env["VAULT_AGENT_TOOL"] = "cursor"
        ref = self.evaluate()
        m = self.manifest(ref)
        machine = m["environment"]["machine"]
        self.assertEqual(machine["tool"], "cursor")
        for key in ("os", "arch", "kernel", "cpu", "cpu_flags", "python", "python_build"):
            self.assertIn(key, machine)
        self.assertEqual((m["runtime"]["name"], m["runtime"]["match"]), ("rt", True))
        import yaml
        dag = yaml.safe_load((self.exp / "research" / "dag.yaml").read_text(encoding="utf-8"))
        entry = dag["nodes"][0]["capsules"][0]
        self.assertEqual(entry["runtime"], {"name": "rt", "match": True})
        self.assertEqual(entry["env"]["tool"], "cursor")

    def test_a_refused_runtime_spends_no_holdout_look(self):
        self.define()
        src = self.base / "src"
        src.mkdir()
        (src / "a.csv").write_text("date,close\n2026-01-01,1\n", encoding="utf-8", newline="\n")
        self.vault("dataset", "create", "px", "--rule", "append-only")
        self.vault("dataset", "add", "px", "--from", str(src))
        self.vault("dataset", "window", "px", "sealed", "--class", "holdout", "--from-date", "2026-01-01",
                   "--to-date", "2026-01-01")
        with open(self.exp / ".gitignore", "a", encoding="utf-8") as f:
            f.write("mounted/\n")
        tev.sh(["git", "commit", "-q", "-am", "mount"], self.exp)
        p = self.vault("run", "--node", "H-1", "--python", sys.executable, "--dataset", "px@latest:mounted/px:sealed",
                       "--", sys.executable, "evaluate.py", check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("cannot be evidence", p.stderr)
        self.assertFalse((self.base / "vault" / "datasets" / "px" / "windows" / "sealed" / "claims").exists())


class TestReplayAndParity(RuntimeTestCase):
    def test_a_replay_rebuilds_the_locked_environment_and_parity_needs_another_machine(self):
        self.define()
        ref = self.evaluate()
        p = self.vault("parity", ref, check=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("has no identical replay", p.stdout)
        p = self.vault("replay", ref, "--to", str(self.base / "same"), "--no-link")
        self.assertIn("uv sync --frozen", p.stdout)
        self.assertIn("Verdict: identical", p.stdout)
        self.assertEqual(self.vault("parity", ref, check=False).returncode, 1, "the same machine and tool is not parity")
        self.env["VAULT_AGENT_TOOL"] = "codex"
        self.vault("replay", ref, "--to", str(self.base / "other"), "--no-link")
        p = self.vault("parity", ref)
        self.assertIn("was replayed identically on another machine", p.stdout)
        retests = [self.manifest(f"H-1/{line.split()[1]}") for line in p.stdout.splitlines() if line.startswith("ok")]
        self.assertEqual(retests[0]["environment"]["machine"]["tool"], "codex")
        self.assertTrue(retests[0]["runtime"]["match"])

    def test_a_replay_outside_the_runtime_is_not_parity(self):
        self.define()
        ref = self.evaluate()
        self.env["VAULT_AGENT_TOOL"] = "codex"
        self.vault("replay", ref, "--setup", "none", "--python", sys.executable, "--to", str(self.base / "r"),
                   "--no-link")
        self.assertEqual(self.vault("parity", ref, check=False).returncode, 1)


class TestUpgrade(RuntimeTestCase):
    """Regression testing: the pinned code with newer packages, compared with what it gave before."""

    def upgraded(self, factor=None):
        up = self.base / "upgrade"
        up.mkdir(exist_ok=True)
        text = (self.exp / "pyproject.toml").read_text(encoding="utf-8")
        if factor:
            text += f"\n[tool.exp]\nfactor = {factor}\n"
        (up / "pyproject.toml").write_text(text, encoding="utf-8", newline="\n")
        shutil.copyfile(self.exp / "uv.lock", up / "uv.lock")
        return up

    def test_an_upgrade_that_changes_nothing_is_identical(self):
        self.define()
        ref = self.evaluate()
        p = self.vault("replay", ref, "--upgrade", str(self.upgraded()), "--to", str(self.base / "r"), "--no-link")
        self.assertIn("Verdict: identical", p.stdout)

    def test_an_upgrade_that_changes_the_result_is_drift_and_never_parity(self):
        self.define()
        self.vault("runtime", "create", "rt2", "--python", self.py, "--profile", "none")
        ref = self.evaluate()
        p = self.vault("replay", ref, "--upgrade", str(self.upgraded(2)), "--runtime", "rt2",
                       "--to", str(self.base / "r"), check=False)
        self.assertEqual(p.returncode, 3)
        self.assertIn("Verdict: drifted", p.stdout)
        retest_id = p.stdout.split("Capsule H-1/", 1)[1].split(":", 1)[0]
        m = self.manifest(f"H-1/{retest_id}")
        self.assertEqual(m["metrics"]["score"], 0.5)
        self.assertEqual((m["upgrade"]["runtime"], m["runtime"]["name"]), ("rt2", "rt2"))
        self.assertEqual(m["comparison"]["verdict"], "drifted")
        import yaml
        dag = yaml.safe_load((self.exp / "research" / "dag.yaml").read_text(encoding="utf-8"))
        self.assertTrue(dag["nodes"][0]["capsules"][-1]["upgrade"])
        self.env["VAULT_AGENT_TOOL"] = "codex"
        self.vault("replay", ref, "--upgrade", str(self.upgraded()), "--to", str(self.base / "r2"), "--no-link")
        self.assertEqual(self.vault("parity", ref, check=False).returncode, 1,
                         "a replay with other packages is a regression test, not parity")

    def test_an_upgrade_needs_the_project_files(self):
        self.define()
        ref = self.evaluate()
        empty = self.base / "empty"
        empty.mkdir()
        p = self.vault("replay", ref, "--upgrade", str(empty), "--to", str(self.base / "r"), check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("must be a folder with pyproject.toml and uv.lock", p.stderr)


@unittest.skipUnless(sys.platform == "linux", "the AVX-512 setting is checked on x86-64 Linux")
class TestNumpySetting(unittest.TestCase):
    def test_the_setting_is_one_this_numpy_accepts(self):
        import vault
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy is not installed")
        value = vault.numpy_setting(sys.executable)
        self.assertIn(value, vault.NUMPY_AVX512_OFF)


if __name__ == "__main__":
    unittest.main()
