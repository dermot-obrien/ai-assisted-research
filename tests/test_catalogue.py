# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""
Tests for datasets read from an external catalogue (references/catalogue.md): a run records the exact
version and digest, the catalogue keeps a reference for the capsule, and a replay reads exactly the files
the run read however the dataset changed since. Run from the repository root:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_experiment_vault as tev  # noqa: E402
from test_datasets import DatasetTestCase  # noqa: E402

# A catalogue in a folder: <root>/<name>/<version>/manifest.json lists the version's files, which sit beside it.
# The digest is the sha256 of manifest.json. References are written under <root>/<name>/refs/<version>/.
FAKE = textwrap.dedent("""\
    import hashlib, json, os, re, shutil, stat
    from pathlib import Path

    ROOT = Path(os.environ["FAKE_CATALOGUE"])

    class Catalogue:
        def _digest(self, name, version):
            return "sha256:" + hashlib.sha256((ROOT / name / version / "manifest.json").read_bytes()).hexdigest()

        def resolve(self, ref):
            body, _, digest = ref.partition("#")
            name, _, version = body.partition("@")
            if not version or version == "latest":
                version = sorted(p.name for p in (ROOT / name).iterdir() if re.fullmatch(r"v[0-9]{4}", p.name))[-1]
            got = self._digest(name, version)
            if digest and digest != got:
                raise ValueError(f"{name}@{version} has digest {got}, not {digest}")
            return {"dataset": name, "version": version, "digest": got}

        def _files(self, name, version):
            return json.loads((ROOT / name / version / "manifest.json").read_text())["files"]

        def materialize(self, ref):
            got = self.resolve(ref)
            name, version = got["dataset"], got["version"]
            out = ROOT / "_cache" / name / version
            if not out.exists():
                out.mkdir(parents=True)
                for path, sha in self._files(name, version).items():
                    src = ROOT / name / "files" / sha
                    assert hashlib.sha256(src.read_bytes()).hexdigest() == sha
                    shutil.copyfile(src, out / path)
                    os.chmod(out / path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            return str(out)

        def damage(self, ref, folder):
            got = self.resolve(ref)
            want = {p: (ROOT / got["dataset"] / "files" / s).stat().st_size
                    for p, s in self._files(got["dataset"], got["version"]).items()}
            have = {f.name: f.stat().st_size for f in Path(folder).iterdir() if f.is_file()}
            return sorted(p for p in set(want) | set(have) if want.get(p) != have.get(p))

        def pin(self, ref, holder, reason, detail):
            if os.environ.get("FAKE_PIN_FAILS"):
                raise RuntimeError("catalogue unreachable")
            got = self.resolve(ref)
            d = ROOT / got["dataset"] / "refs" / got["version"]
            d.mkdir(parents=True, exist_ok=True)
            (d / f"capsule-{holder}.json").write_text(json.dumps({"reason": reason, **detail}))
    """)

READ = textwrap.dedent("""\
    import json, os
    spec = json.load(open(os.environ["VAULT_DATASETS"]))["bars"]
    rows = []
    for f in sorted(os.listdir(spec["path"])):
        rows += [l for l in open(os.path.join(spec["path"], f)).read().splitlines() if l and not l.startswith("date")]
    os.makedirs("out", exist_ok=True)
    json.dump({"rows": len(rows), "total": sum(float(r.split(",")[1]) for r in rows),
               "files": sorted(os.listdir(spec["path"]))}, open("out/metrics.json", "w"))
    """)


class CatalogueTestCase(DatasetTestCase):
    def setUp(self):
        super().setUp()
        self.cat = self.base / "catalogue"
        (self.cat / "bars" / "files").mkdir(parents=True)
        plugin = self.base / "plugin"
        plugin.mkdir()
        (plugin / "fakecat.py").write_text(FAKE, encoding="utf-8", newline="\n")
        self.env["FAKE_CATALOGUE"] = str(self.cat)
        (self.exp / "read.py").write_text(READ, encoding="utf-8", newline="\n")
        tev.sh(["git", "add", "-A"], self.exp)
        tev.sh(["git", "commit", "-q", "-m", "read"], self.exp)
        self.configure()
        self.publish("v0001", {"AAA.csv": "date,close\n2026-01-01,10\n2026-01-02,11\n"})

    def configure(self, inputs="any"):
        (self.exp / "research.yaml").write_text(
            "dag_path: research/dag.yaml\nnode_index_path: research/index.yaml\nwork_items_path: work/\n"
            f"vault:\n  inputs: {inputs}\n  catalogue:\n    name: lake\n    adapter: fakecat:Catalogue\n"
            f"    python_path: [{json.dumps(str(self.base / 'plugin'))}]\n", encoding="utf-8", newline="\n")

    def publish(self, version, files):
        listed = {}
        for path, text in files.items():
            sha = hashlib.sha256(text.encode()).hexdigest()
            (self.cat / "bars" / "files" / sha).write_text(text, encoding="utf-8", newline="")
            listed[path] = sha
        (self.cat / "bars" / version).mkdir()
        (self.cat / "bars" / version / "manifest.json").write_text(json.dumps({"files": listed}), encoding="utf-8")

    def digest(self, version):
        return hashlib.sha256((self.cat / "bars" / version / "manifest.json").read_bytes()).hexdigest()

    def read(self, ref="bars", *extra, check=True, node="H-1"):
        p = self.vault("run", "--node", node, "--from-catalogue", f"mounted/bars={ref}", "--outputs", "out",
                       "--metrics", "out/metrics.json", "--metric", "rows", "--no-link", *extra, "--",
                       sys.executable, "read.py", check=check)
        if not check:
            return p
        return p.stdout.split("Capsule ", 1)[1].split(":", 1)[0]


class TestCatalogueRuns(CatalogueTestCase):
    def test_a_run_records_the_exact_version_and_digest_and_the_catalogue_keeps_it(self):
        ref = self.read("bars")  # unpinned: resolved to the latest at the start of the run
        m = self.manifest(ref)
        d = m["datasets"][0]
        self.assertEqual((d["catalogue"], d["dataset"], d["version"], d["sha256"]), ("lake", "bars", "v0001", self.digest("v0001")))
        self.assertEqual(d["reference"], f"bars@v0001#sha256:{self.digest('v0001')}")
        self.assertNotIn("data", [k for k, v in m.items() if v], "nothing is copied into the capsule")
        pins = list((self.cat / "bars" / "refs" / "v0001").iterdir())
        self.assertEqual(len(pins), 1)
        self.assertTrue(pins[0].name.startswith("capsule-") and len(pins[0].stem) == len("capsule-") + 64)
        self.assertFalse((self.base / "vault" / "datasets").exists(), "a catalogue version is not a vault dataset")

    def test_a_replay_reads_exactly_the_original_files_after_the_dataset_grows_and_is_revised(self):
        ref = self.read("bars")
        before = json.loads((self.exp / "out" / "metrics.json").read_text())
        # The dataset grows (a new file) and is revised (the old file replaced) in later versions.
        self.publish("v0002", {"AAA.csv": "date,close\n2026-01-01,10\n2026-01-02,11\n",
                               "BBB.csv": "date,close\n2026-01-03,5\n"})
        self.publish("v0003", {"AAA.csv": "date,close\n2026-01-01,99\n", "BBB.csv": "date,close\n2026-01-03,5\n"})
        p = self.vault("replay", ref, "--setup", "none", "--no-record", "--to", str(self.base / "replay"))
        self.assertIn("identical", p.stdout)
        after = json.loads((self.base / "replay" / "repos" / "exp" / "out" / "metrics.json").read_text())
        self.assertEqual(after, before)
        self.assertEqual(after["files"], ["AAA.csv"], "files added later are not in the version the capsule names")
        self.assertIn("ok", self.vault("verify", ref, "--deep").stdout)

    def test_a_version_whose_manifest_changed_is_refused_by_replay_and_verify(self):
        ref = self.read("bars@v0001")
        manifest = self.cat / "bars" / "v0001" / "manifest.json"
        manifest.write_text(manifest.read_text().replace("}}", ', "ZZZ.csv": "00"}}'), encoding="utf-8")
        p = self.vault("replay", ref, "--setup", "none", "--no-record", "--to", str(self.base / "r2"), check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("catalogue refused", p.stderr)
        p = self.vault("verify", ref, check=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn("FAIL", p.stdout)

    def test_a_reference_with_another_digest_is_refused_before_the_run(self):
        p = self.read("bars@v0001#sha256:" + "0" * 64, check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("catalogue refused", p.stderr)

    def test_a_failed_pin_keeps_the_capsule_and_vault_pin_records_it_later(self):
        self.env["FAKE_PIN_FAILS"] = "1"
        p = self.read("bars", check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("did not record that it reads", p.stderr)
        cid = p.stdout.split("Capsule ", 1)[1].split(":", 1)[0]
        del self.env["FAKE_PIN_FAILS"]
        self.assertIn("1 catalogue reference(s) recorded", self.vault("pin", cid).stdout)
        self.assertEqual(len(list((self.cat / "bars" / "refs" / "v0001").iterdir())), 1)


class TestCatalogueInputs(CatalogueTestCase):
    def test_catalogue_inputs_refuse_copied_data_unless_the_experiment_produced_it(self):
        self.configure(inputs="catalogue")
        p = self.read("bars", "--data", "data", check=False)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("vault.inputs is catalogue", p.stderr)
        ref = self.read("bars", "--data", "data", "--produced-data")
        self.assertEqual(self.manifest(ref)["data_origin"], "produced")

    def test_a_dry_run_names_the_resolved_version(self):
        p = self.read("bars", "--dry-run", check=False)
        self.assertIn(f"dataset bars@v0001#sha256:{self.digest('v0001')} from catalogue lake", p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
