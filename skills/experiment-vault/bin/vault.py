#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""
The experiment vault: everything a hypothesis test used and produced, kept as one
self-contained, immutable capsule in cheap cloud storage, so any later agent can
restore it and run the experiment again.

A capsule holds the exact code (every repository at its commit, tagged vault/<commit12>,
with the vault keeping each repository's history as incremental git bundles, so a new
commit costs only its changes; restore checks the commit's git tree), the data the run read, the Python environment (the
interpreter, a frozen package list and, optionally, the wheels themselves), the
hardware, the command, its seeds and settings, its console output, the outputs it
wrote and the metrics it reported. Files are stored once by their SHA-256, so data
and wheels shared by many capsules cost one copy. A capsule's manifest is written
last and never overwritten, and its id carries the manifest's hash.

    <vault>/VAULT.md                                       the format, for a reader without this tool
    <vault>/blobs/sha256/<hex>                             every file, by content, never overwritten
    <vault>/repos/<root commit>/<tip commit>.bundle        a repository's history, in increments
    <vault>/capsules/<project>/<node>/<stamp>-<hash12>.json one manifest per run or retest

The vault is a folder (a path or file://) or a Google Cloud Storage prefix
(gs://bucket/prefix, through the gcloud CLI). Both use the same layout, so a local
vault can be copied up with `gcloud storage rsync`.

Usage:
    python vault.py init
    python vault.py run --node H-001 --data data/ --outputs out/ --metrics out/metrics.json -- python train.py --seed 7
    python vault.py capture --node H-001 --cmd "python train.py --seed 7" --outputs out/ --metrics out/metrics.json
    python vault.py list [--node H-001] [--long]
    python vault.py show <capsule>
    python vault.py verify <capsule> [--deep]        or  verify --node H-001  or  verify --all
    python vault.py restore <capsule> --to <dir>
    python vault.py replay <capsule> [--setup venv|none] [--pip REQ ...] [--no-record]
    python vault.py coverage [--verify] [--strict]
    python vault.py lifecycle

<capsule> is a capsule id, <node>/<id>, or the manifest's URI. Every command takes
--vault and --project, which override $RESEARCH_VAULT, research.yaml's vault.uri and
vault.project (or dag_project).
"""
from __future__ import annotations

import argparse
import atexit
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Iterable

FORMAT = "experiment-vault/2"
FORMATS = ("experiment-vault/1", "experiment-vault/2")
TOOL_VERSION = "1.2.0"

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CAPSULE_RE = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{12}$")
HEX_RE = re.compile(r"^[0-9a-f]{64}$")

# Environment variables that change results and are recorded whenever they are set.
RECORDED_ENV = ("PYTHONHASHSEED", "CUBLAS_WORKSPACE_CONFIG", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                "OPENBLAS_NUM_THREADS", "CUDA_VISIBLE_DEVICES", "TZ", "LANG", "LC_ALL")
SECRET_HINT = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)", re.I)
PYTHON_NAMES = {"python", "python3", "python.exe", "python3.exe", "py"}

# A service account key for the vault, as JSON in the variable, or as a file named by the other.
# A cloud session, whose setup script cannot read saved secrets, gets the key this way.
KEY_VARS = ("RESEARCH_VAULT_GCP_KEY", "RESEARCH_VAULT_GCP_KEY_FILE")

VAULT_README = """# Experiment vault

Capsules of hypothesis experiments: everything a run used and produced, so it can be run again.
Written by the experiment-vault skill (`vault.py`); nothing here is edited or overwritten.

## Format (for an agent without the skill)

    blobs/sha256/<hex>                               a file, named by the SHA-256 of its content
    repos/<root commit>/<tip commit>.bundle          a repository's history, as incremental git bundles
    capsules/<project>/<node>/<stamp>-<hash12>.json  a manifest, one per run or retest

A manifest is JSON (`format: experiment-vault/2`; 1 is read too). `<hash12>` is the first 12 hex digits of the
SHA-256 of the manifest file's bytes, so a manifest proves its own integrity, and the hypothesis
DAG records the full hash beside the capsule id. Every file the manifest names is a blob:

| Section | Holds |
|---|---|
| `node` | The hypothesis node id, a snapshot of the node and the DAG store commit at capture |
| `code` | Per repository: remote, commit, tree, and either `bundles` (the tip commits of the bundles under `repos/<root>/` that hold the commit) or `archive`, a tar.gz of the commit |
| `data` | Files the run read: `path` relative to the main repository, `sha256`, `size` |
| `environment` | Interpreter, platform, `lock` (pip freeze), optional `wheels`, hardware |
| `run` | `argv`, `cwd`, recorded `env`, `seeds`, times, `exit_code`, `stdout` and `stderr` blobs |
| `outputs`, `metrics` | Files the run wrote, and the metrics it reported |
| `comparison` | On a retest: the capsule it retested and whether the result reproduced |

To restore by hand: for each `code[]` entry with `bundles`, `git init repos/<name>`, then
`git fetch <bundle> '+refs/tags/*:refs/tags/*'` for each bundle (a bundle whose prerequisites
are missing waits for the others) and `git checkout --detach <commit>`; or untar its `archive`.
Then copy each `data[]`
blob to `repos/<main>/<path>`, install `environment.lock` (from `environment.wheels` with
`pip install --no-index --find-links`), and run `run.argv` in `repos/<main>/<run.cwd>`.
"""


class VaultError(Exception):
    pass


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def canonical(manifest: dict) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def run_cmd(argv: list[str], cwd: Path | str | None = None, check: bool = True,
            input_text: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    exe = shutil.which(argv[0]) or argv[0]
    try:
        p = subprocess.run([exe, *argv[1:]], cwd=cwd, input=input_text, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", env=env)
    except FileNotFoundError as e:
        raise VaultError(f"{argv[0]} is not installed or not on PATH") from e
    if check and p.returncode != 0:
        raise VaultError(f"{' '.join(argv[:4])} failed: {(p.stderr or p.stdout).strip()[:500]}")
    return p


# ---------------------------------------------------------------- configuration

def find_research_yaml() -> Path | None:
    env = os.environ.get("RMS_ROOT")
    if env:
        p = Path(env).expanduser() / "research.yaml"
        return p if p.is_file() else None
    d = Path.cwd().resolve()
    for parent in [d, *d.parents]:
        if (parent / "research.yaml").is_file():
            return parent / "research.yaml"
    return None


def read_yaml(path: Path) -> Any:
    try:
        import yaml
    except ImportError as e:
        raise VaultError("PyYAML is not installed. Run: python -m pip install PyYAML") from e
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class Settings:
    def __init__(self, args: argparse.Namespace):
        self.research_yaml = find_research_yaml()
        cfg: dict = {}
        if self.research_yaml:
            try:
                cfg = read_yaml(self.research_yaml) or {}
            except VaultError:
                raise
            except Exception as e:  # noqa: BLE001 - an unreadable research.yaml is reported, not fatal
                print(f"warning: {self.research_yaml} could not be read ({e}); ignoring it", file=sys.stderr)
        self.root = self.research_yaml.parent if self.research_yaml else None
        vault = cfg.get("vault") if isinstance(cfg.get("vault"), dict) else {}
        self.uri = getattr(args, "vault", None) or os.environ.get("RESEARCH_VAULT")
        if not self.uri and vault.get("uri"):
            self.uri = str(vault["uri"])
            # A relative vault in research.yaml is relative to research.yaml, like every path in it.
            if "://" not in self.uri and not os.path.isabs(self.uri):
                self.uri = str((self.root / self.uri).resolve())
        self.project = (getattr(args, "project", None) or os.environ.get("RESEARCH_VAULT_PROJECT")
                        or vault.get("project") or cfg.get("dag_project"))
        self.vendor_wheels = bool(vault.get("vendor_wheels", False))
        self.code_storage = str(vault.get("code_storage", "bundle"))
        if self.code_storage not in ("bundle", "archive"):
            raise VaultError(f"vault.code_storage is {self.code_storage!r}; use bundle or archive")
        self.rtol = float(vault.get("rtol", 1e-9))
        self.atol = float(vault.get("atol", 1e-12))
        self.dag_path = (self.root / cfg["dag_path"]) if self.root and cfg.get("dag_path") else None
        # Files the research tools rewrite; a change to them does not make the code dirty.
        self.managed = {(self.root / cfg[k]).resolve() for k in ("dag_path", "node_index_path")
                        if self.root and isinstance(cfg.get(k), str)}

    def need(self, project: bool = True) -> None:
        if not self.uri:
            raise VaultError("no vault configured: pass --vault, set $RESEARCH_VAULT, or add vault.uri to research.yaml")
        if project:
            if not self.project:
                raise VaultError("no project: pass --project, or set vault.project (or dag_project) in research.yaml")
            if not NAME_RE.match(self.project):
                raise VaultError(f"project {self.project!r} must be letters, digits, '.', '_' or '-'")


# ---------------------------------------------------------------- backends

class Backend:
    """A place keys are written once and read back. Keys use '/' and never start with it."""

    uri: str

    def url(self, key: str) -> str:
        raise NotImplementedError

    def read(self, key: str) -> bytes | None:
        raise NotImplementedError

    def write_once(self, key: str, data: bytes) -> bool:
        """Write data at key unless the key exists. True when this call wrote it."""
        raise NotImplementedError

    def put_files(self, files: dict[str, Path]) -> int:
        """Upload {key: local path}, skipping keys already there. Returns the count sent."""
        raise NotImplementedError

    def get_keys(self, keys: Iterable[str], into: Path) -> None:
        """Download keys into the folder `into`, each named by the last part of its key."""
        raise NotImplementedError

    def missing(self, keys: Iterable[str]) -> list[str]:
        raise NotImplementedError

    def put_blobs(self, files: dict[str, Path]) -> int:
        """Upload {hex: local path} into blobs/sha256/, skipping blobs already there. Returns the count sent."""
        return self.put_files({f"blobs/sha256/{h}": p for h, p in files.items()})

    def get_blobs(self, hexes: Iterable[str], into: Path) -> None:
        """Download blobs into the folder `into`, each named by its hex."""
        self.get_keys([f"blobs/sha256/{h}" for h in set(hexes)], into)

    def missing_blobs(self, hexes: Iterable[str]) -> list[str]:
        return sorted(k.rsplit("/", 1)[1] for k in self.missing(f"blobs/sha256/{h}" for h in set(hexes)))

    def list(self, prefix: str) -> list[str]:
        raise NotImplementedError


class LocalBackend(Backend):
    def __init__(self, root: Path):
        self.root = root
        self.uri = str(root)

    def url(self, key: str) -> str:
        return (self.root / key).as_posix()

    def read(self, key: str) -> bytes | None:
        p = self.root / key
        return p.read_bytes() if p.is_file() else None

    def write_once(self, key: str, data: bytes) -> bool:
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o444)
        except FileExistsError:
            return False
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return True

    def put_files(self, files: dict[str, Path]) -> int:
        sent = 0
        for key, src in files.items():
            dest = self.root / key
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.parent / f".{dest.name}.{secrets.token_hex(4)}.tmp"
            shutil.copyfile(src, tmp)
            os.chmod(tmp, 0o444)
            try:
                os.replace(tmp, dest) if not dest.exists() else os.remove(tmp)
            except OSError:
                if tmp.exists():
                    os.remove(tmp)
            sent += 1
        return sent

    def get_keys(self, keys: Iterable[str], into: Path) -> None:
        into.mkdir(parents=True, exist_ok=True)
        for key in set(keys):
            src = self.root / key
            if not src.is_file():
                raise VaultError(f"{key} is missing from {self.uri}")
            shutil.copyfile(src, into / key.rsplit("/", 1)[-1])

    def missing(self, keys: Iterable[str]) -> list[str]:
        return sorted(k for k in set(keys) if not (self.root / k).is_file())

    def list(self, prefix: str) -> list[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        return sorted(p.relative_to(self.root).as_posix() for p in base.rglob("*") if p.is_file())


class GCSBackend(Backend):
    """Google Cloud Storage through the gcloud CLI, so no Python client library is needed."""

    CHUNK = 200

    def __init__(self, uri: str):
        m = re.match(r"^gs://([^/]+)/?(.*)$", uri)
        if not m:
            raise VaultError(f"not a gs:// URI: {uri}")
        self.bucket, prefix = m.group(1), m.group(2).strip("/")
        self.base = f"gs://{self.bucket}/{prefix + '/' if prefix else ''}"
        self.uri = self.base.rstrip("/")
        if not shutil.which("gcloud"):
            raise VaultError("gcloud is not installed or not on PATH; it is needed for a gs:// vault")
        self.env = gcloud_env()

    def gcloud(self, args: list[str], check: bool = True, input_text: str | None = None):
        return run_cmd(["gcloud", *args], check=check, input_text=input_text, env=self.env)

    def url(self, key: str) -> str:
        return self.base + key

    def read(self, key: str) -> bytes | None:
        p = subprocess.run([shutil.which("gcloud"), "storage", "cat", self.url(key)], capture_output=True,
                           env=self.env)
        if p.returncode != 0:
            err = p.stderr.decode("utf-8", "replace")
            if any(t in err.lower() for t in ("no urls matched", "matched no objects", "404", "not found")):
                return None
            raise VaultError(f"gcloud storage cat {self.url(key)} failed: {err.strip()[:300]}")
        return p.stdout

    def write_once(self, key: str, data: bytes) -> bool:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "object"
            tmp.write_bytes(data)
            p = self.gcloud(["storage", "cp", "--if-generation-match=0", str(tmp), self.url(key)], check=False)
        if p.returncode == 0:
            return True
        if self.read(key) is not None:
            return False
        raise VaultError(f"could not write {self.url(key)}: {(p.stderr or p.stdout).strip()[:300]}")

    def put_files(self, files: dict[str, Path]) -> int:
        # --no-clobber skips every object already in the bucket, so nothing is listed first.
        # One copy per destination folder, so a capsule's blobs go up in one call.
        by_dir: dict[str, dict[str, Path]] = {}
        for key, src in files.items():
            folder, _, name = key.rpartition("/")
            by_dir.setdefault(folder, {})[name] = src
        sent = 0
        for folder, named in by_dir.items():
            with tempfile.TemporaryDirectory() as td:
                staged = []
                for name, src in named.items():
                    dest = Path(td) / name
                    try:
                        os.link(src, dest)
                    except OSError:
                        shutil.copyfile(src, dest)
                    staged.append(str(dest))
                p = self.gcloud(["storage", "cp", "--no-clobber", "-I", self.url(folder + "/")],
                                input_text="\n".join(staged) + "\n")
            sent += len(named) - len(re.findall(r"(?i)skipping existing", p.stdout + p.stderr))
        return sent

    def existing(self, keys: Iterable[str]) -> list[str]:
        found: list[str] = []
        keys = sorted(set(keys))
        for i in range(0, len(keys), self.CHUNK):
            chunk_keys = keys[i:i + self.CHUNK]
            p = self.gcloud(["storage", "ls", *[self.url(k) for k in chunk_keys]], check=False)
            listed = {line.strip()[len(self.base):] for line in p.stdout.splitlines()
                      if line.strip().startswith(self.base)}
            chunk = [k for k in chunk_keys if k in listed]
            if p.returncode != 0:
                # ls may stop at the first missing URL; ask about the rest one at a time.
                for k in chunk_keys:
                    if k not in listed and self.gcloud(["storage", "objects", "describe", self.url(k)],
                                                       check=False).returncode == 0:
                        chunk.append(k)
            found.extend(chunk)
        return found

    def missing(self, keys: Iterable[str]) -> list[str]:
        keys = set(keys)
        return sorted(keys - set(self.existing(keys)))

    def get_keys(self, keys: Iterable[str], into: Path) -> None:
        into.mkdir(parents=True, exist_ok=True)
        urls = [self.url(k) for k in sorted(set(keys))]
        if urls:
            self.gcloud(["storage", "cp", "-I", str(into) + os.sep], input_text="\n".join(urls) + "\n")

    def list(self, prefix: str) -> list[str]:
        p = self.gcloud(["storage", "ls", self.url(prefix) + "**"], check=False)
        if p.returncode != 0:
            return []
        return sorted(line.strip()[len(self.base):] for line in p.stdout.splitlines()
                      if line.strip().startswith(self.base) and not line.strip().endswith("/"))


def gcloud_env() -> dict | None:
    """The environment for the vault's own gcloud calls: with a key in RESEARCH_VAULT_GCP_KEY (or a file
    in RESEARCH_VAULT_GCP_KEY_FILE), gcloud authenticates as that service account for these calls only,
    through auth/credential_file_override, leaving the machine's own gcloud sign-in as it is. Without
    one, None: gcloud uses whatever account is signed in."""
    text = os.environ.get("RESEARCH_VAULT_GCP_KEY")
    path = os.environ.get("RESEARCH_VAULT_GCP_KEY_FILE")
    if not text and not path:
        return None
    if not text:
        if not os.path.isfile(path):
            raise VaultError(f"RESEARCH_VAULT_GCP_KEY_FILE names {path}, which does not exist")
        key_file = path
    else:
        text = text.strip()
        if not text.startswith("{"):
            # Base64 of the key file: one line, with no characters a settings field can mangle.
            import base64
            import binascii
            try:
                text = base64.b64decode(text, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError):
                raise VaultError("RESEARCH_VAULT_GCP_KEY is neither JSON nor base64 JSON: set it to the service "
                                 "account key file's JSON on one line, or to the file in base64") from None
        try:
            key = json.loads(text)
        except json.JSONDecodeError:
            raise VaultError("RESEARCH_VAULT_GCP_KEY is not JSON: set it to the service account key file's JSON "
                             "on one line, or to the file in base64") from None
        if not isinstance(key, dict) or key.get("type") != "service_account" or "private_key" not in key:
            raise VaultError("RESEARCH_VAULT_GCP_KEY is not a service account key (its type must be "
                             "service_account)")
        fd, key_file = tempfile.mkstemp(prefix="vault-key-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(key_file, 0o600)
        atexit.register(lambda: os.path.exists(key_file) and os.remove(key_file))
    env = without_vault_keys(os.environ)
    env["CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE"] = key_file
    return env


def without_vault_keys(environ) -> dict:
    """A copy of the environment without the vault's key, for anything the vault starts but gcloud."""
    return {k: v for k, v in environ.items() if k not in KEY_VARS}


def open_backend(uri: str) -> Backend:
    if uri.startswith("gs://"):
        return GCSBackend(uri)
    if uri.startswith("file://"):
        uri = uri[len("file://"):]
    if "://" in uri:
        raise VaultError(f"unsupported vault URI {uri}: use a folder, file:// or gs://")
    return LocalBackend(Path(uri).expanduser().resolve())


# ---------------------------------------------------------------- git and the exact code

def git(args: list[str], cwd: Path, check: bool = True) -> str:
    return run_cmd(["git", *args], cwd=cwd, check=check).stdout.strip()


def strip_credentials(url: str) -> str:
    return re.sub(r"^(\w+://)[^/@]+@", r"\1", url)


def git_tree_hash(entries: dict[str, tuple[str, bytes]], algo: str) -> str:
    """The git tree hash of {path: (mode, object id bytes)} for files, symlinks and gitlinks."""
    tree: dict = {}
    for path, (mode, oid) in entries.items():
        parts = path.split("/")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = (mode, oid)

    def build(node: dict) -> bytes:
        items = []
        for name, value in node.items():
            if isinstance(value, dict):
                items.append((name + "/", b"40000 " + name.encode() + b"\0" + build(value)))
            else:
                mode, oid = value
                items.append((name, mode.encode() + b" " + name.encode() + b"\0" + oid))
        body = b"".join(entry for _, entry in sorted(items, key=lambda t: t[0].encode()))
        return hashlib.new(algo, b"tree %d\0" % len(body) + body).digest()

    return build(tree).hex()


def tar_tree_hash(tar_path: Path, gitlinks: dict[str, str], algo: str) -> str:
    entries: dict[str, tuple[str, bytes]] = {}
    with tarfile.open(tar_path) as tf:
        for m in tf.getmembers():
            if m.isdir() or m.type in (tarfile.XGLTYPE, tarfile.XHDTYPE):
                continue
            if m.issym():
                content, mode = m.linkname.encode(), "120000"
            elif m.isfile():
                content = tf.extractfile(m).read()
                mode = "100755" if m.mode & 0o111 else "100644"
            else:
                continue
            oid = hashlib.new(algo, b"blob %d\0" % len(content) + content).digest()
            entries[m.name.rstrip("/")] = (mode, oid)
    for path, sha in gitlinks.items():
        entries[path] = ("160000", bytes.fromhex(sha))
    return git_tree_hash(entries, algo)


def capture_repo(path: Path, name: str, allow_dirty: bool, work: Path, blobs: dict[str, Path],
                 managed: set[Path] = frozenset(), backend: Backend | None = None,
                 files: dict[str, Path] | None = None, storage: str = "bundle", push_tag: bool = True,
                 dry: bool = False) -> dict:
    """Pin one repository at its commit.

    storage "bundle" (the default) keeps the code as git history: the commit is tagged
    vault/<commit12> (and the tag pushed to origin, so a deleted branch cannot lose it), and
    the vault holds incremental git bundles per repository, under repos/<root commit>/, so a
    new capsule adds only the commits the vault lacks. storage "archive", and any shallow
    clone, keeps a compressed tar of the commit instead.
    """
    top = Path(git(["rev-parse", "--show-toplevel"], path))
    commit = git(["rev-parse", "HEAD"], top)
    tree = git(["rev-parse", "HEAD^{tree}"], top)
    algo = git(["rev-parse", "--show-object-format"], top, check=False) or "sha1"
    entry: dict[str, Any] = {"name": name, "commit": commit, "tree": tree, "object_format": algo}
    remote = git(["remote", "get-url", "origin"], top, check=False)
    if remote:
        entry["remote"] = strip_credentials(remote)
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], top, check=False)
    if branch and branch != "HEAD":
        entry["branch"] = branch
    if remote:
        contains = git(["branch", "-r", "--contains", commit], top, check=False)
        entry["pushed"] = bool(contains.strip())
    # The settings that decide the bytes git checks out, so a restore writes the files the run read.
    checkout = {k: v for k in ("core.autocrlf", "core.eol")
                if (v := git(["config", "--get", k], top, check=False))}
    if checkout:
        entry["checkout"] = checkout
    status = "\n".join(line for line in run_cmd(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=top).stdout.splitlines()
                       if (top / line[3:].strip('"')).resolve() not in managed)
    entry["dirty"] = bool(status)
    if status and not allow_dirty:
        raise VaultError(f"{top} has uncommitted changes. Commit them (the capsule pins a commit), "
                         f"or pass --allow-dirty to store the difference as a patch.")
    gitlinks = {}
    for line in git(["ls-tree", "-r", commit], top).splitlines():
        meta, _, path_ = line.partition("\t")
        mode, kind, sha = meta.split()
        if mode == "160000":
            gitlinks[path_] = sha
    if gitlinks:
        entry["submodules"] = gitlinks
    if storage == "bundle" and git(["rev-parse", "--is-shallow-repository"], top, check=False) == "true":
        print(f"warning: {top} is a shallow clone, so its history cannot be bundled; keeping a compressed "
              f"snapshot of {commit[:12]} instead. Run `git fetch --unshallow` to store history next time.",
              file=sys.stderr)
        storage = "archive"
    if dry:
        entry["storage"] = storage
        if storage == "bundle" and backend is not None:
            entry["new_commits"] = commits_to_bundle(top, commit, backend)
        return entry
    if storage == "bundle" and backend is not None and files is not None:
        entry.update(bundle_repo(top, commit, backend, files, work, push_tag and bool(remote)))
    else:
        entry.update(archive_repo(top, name, commit, tree, algo, gitlinks, work, blobs))
    if status:
        diff_path = work / f"{name}.patch"
        diff_path.write_bytes(subprocess.run([shutil.which("git") or "git", "diff", "--binary", "HEAD"],
                                             cwd=top, capture_output=True).stdout)
        hexd, size = sha256_file(diff_path)
        blobs[hexd] = diff_path
        entry["patch"] = {"sha256": hexd, "size": size}
        untracked = []
        for rel in git(["ls-files", "--others", "--exclude-standard"], top).splitlines():
            f = top / rel
            if f.is_file():
                hexd, size = sha256_file(f)
                blobs[hexd] = f
                untracked.append({"path": rel, "sha256": hexd, "size": size})
        entry["untracked"] = untracked
    return entry


def archive_repo(top: Path, name: str, commit: str, tree: str, algo: str, gitlinks: dict[str, str],
                 work: Path, blobs: dict[str, Path]) -> dict:
    """A gzip-compressed tar of the commit, with exact: true when its git tree hash is the commit's."""
    tar_path = work / f"{name}.tar"
    with open(tar_path, "wb") as f:
        p = subprocess.run([shutil.which("git") or "git", "-c", "core.autocrlf=false", "archive",
                            "--format=tar", commit], cwd=top, stdout=f, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise VaultError(f"git archive failed in {top}: {p.stderr.decode('utf-8', 'replace')[:300]}")
    exact = tar_tree_hash(tar_path, gitlinks, algo) == tree
    gz_path = work / f"{name}.tar.gz"
    # mtime 0 and no file name, so the same commit always compresses to the same bytes.
    with open(tar_path, "rb") as src, open(gz_path, "wb") as raw, \
            gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        shutil.copyfileobj(src, gz)
    tar_path.unlink()
    if not exact:
        print(f"warning: the archive of {name} differs from commit {commit[:12]}'s tree "
              f"(export-ignore, export-subst or eol attributes); the commit is still recorded", file=sys.stderr)
    hexd, size = sha256_file(gz_path)
    blobs[hexd] = gz_path
    return {"storage": "archive", "archive": {"sha256": hexd, "size": size, "format": "tar.gz"}, "exact": exact}


def bundle_key(root: str, tip: str) -> str:
    return f"repos/{root}/{tip}.bundle"


def vault_tips(top: Path, commit: str, backend: Backend) -> tuple[str, list[str], list[str]]:
    """(root commit, tips the vault holds for this repository, those of them present locally)."""
    root = sorted(git(["rev-list", "--max-parents=0", commit], top).split())[0]
    prefix = f"repos/{root}/"
    known = sorted({k[len(prefix):-len(".bundle")] for k in backend.list(prefix) if k.endswith(".bundle")})
    local = [t for t in known if run_cmd(["git", "cat-file", "-e", f"{t}^{{commit}}"], cwd=top,
                                          check=False).returncode == 0]
    return root, known, local


def commits_to_bundle(top: Path, commit: str, backend: Backend) -> int:
    """How many commits a capture of this commit would add to the vault."""
    _, known, local = vault_tips(top, commit, backend)
    if commit in known:
        return 0
    return int(git(["rev-list", "--count", commit, *[f"^{t}" for t in local]], top) or 0)


def bundle_repo(top: Path, commit: str, backend: Backend, files: dict[str, Path], work: Path,
                push: bool) -> dict:
    """Tag the commit and add a git bundle of the commits the vault does not hold yet."""
    root, known, local = vault_tips(top, commit, backend)
    tag = f"vault/{commit[:12]}"
    at = git(["rev-parse", "-q", "--verify", f"refs/tags/{tag}^{{commit}}"], top, check=False)
    if at and at != commit:
        tag = f"vault/{commit}"
        at = git(["rev-parse", "-q", "--verify", f"refs/tags/{tag}^{{commit}}"], top, check=False)
    if not at:
        git(["tag", tag, commit], top)
    covered = commit in known or (local and not git(["rev-list", "-n", "1", commit, "--not", *local], top))
    if not covered:
        path = work / f"{commit}.bundle"
        p = run_cmd(["git", "bundle", "create", str(path), f"refs/tags/{tag}", *[f"^{t}" for t in local]],
                    cwd=top, check=False)
        if p.returncode != 0:
            raise VaultError(f"git bundle failed in {top}: {(p.stderr or p.stdout).strip()[:300]}")
        files[bundle_key(root, commit)] = path
        known = sorted({*known, commit})
    entry: dict[str, Any] = {"storage": "bundle", "root": root, "bundles": known, "tag": tag, "exact": True}
    if push:
        p = run_cmd(["git", "push", "-q", "origin", f"refs/tags/{tag}"], cwd=top, check=False)
        entry["tag_pushed"] = p.returncode == 0
        if p.returncode != 0:
            print(f"warning: could not push tag {tag} to origin ({(p.stderr or p.stdout).strip()[:200]}); "
                  f"the vault's bundles still hold the commit", file=sys.stderr)
    return entry


def restore_bundled(backend: Backend, repo: dict, target: Path, cache: Path) -> None:
    """Rebuild the repository from its bundles, check out the commit, and prove its tree."""
    folder = cache / "bundles" / repo["root"]
    backend.get_keys([bundle_key(repo["root"], t) for t in repo["bundles"]], folder)
    init = ["git", "init", "-q"]
    if repo.get("object_format") == "sha256":
        init.append("--object-format=sha256")
    run_cmd([*init, str(target)])
    pending = sorted(folder.glob("*.bundle"))
    while pending:
        # A bundle applies once the commits it builds on are in place; repeat until all have.
        ready = [b for b in pending if run_cmd(["git", "bundle", "verify", "-q", str(b)], cwd=target,
                                                check=False).returncode == 0]
        if not ready:
            raise VaultError(f"{len(pending)} bundle(s) of {repo['name']} need commits the vault does not hold: "
                             f"{', '.join(b.stem[:12] for b in pending[:3])}")
        for b in ready:
            run_cmd(["git", "fetch", "-q", str(b), "+refs/tags/*:refs/tags/*"], cwd=target)
            pending.remove(b)
    # The capture machine's end-of-line settings, never the restoring machine's.
    settings = {"core.autocrlf": "false", **repo.get("checkout", {})}
    config = [arg for k, v in settings.items() for arg in ("-c", f"{k}={v}")]
    run_cmd(["git", *config, "-c", "advice.detachedHead=false", "checkout", "-q", "--detach", repo["commit"]],
            cwd=target)
    # Keep the settings in the restored repository, so git status agrees with the files.
    for k, v in settings.items():
        run_cmd(["git", "config", k, v], cwd=target)
    tree = git(["rev-parse", f"{repo['commit']}^{{tree}}"], target)
    if tree != repo["tree"]:
        raise VaultError(f"{repo['name']} restored to tree {tree[:12]}, not the recorded {repo['tree'][:12]}")


def iter_bundle_keys(manifest: dict) -> Iterable[str]:
    for repo in manifest.get("code", []):
        for tip in repo.get("bundles", []):
            yield bundle_key(repo["root"], tip)


def repos_to_capture(root: Path, extras: list[str]) -> list[tuple[Path, str, str | None]]:
    """(path, name, path relative to the main repository) for the main repository, every --repo,
    and every submodule of any of them, recursively. A submodule that is not checked out is an error:
    its code would be missing from the capsule."""
    out: list[tuple[Path, str, str | None]] = [(root, root.name, None)]
    for i, extra in enumerate(extras):
        r = Path(git(["rev-parse", "--show-toplevel"], Path(extra).resolve())).resolve()
        name = r.name if r.name not in {n for _, n, _ in out} else f"{r.name}-{i}"
        out.append((r, name, os.path.relpath(r, root).replace(os.sep, "/")))
    queue = list(out)
    while queue:
        top, name, _ = queue.pop(0)
        for line in git(["ls-tree", "-r", "HEAD"], top).splitlines():
            meta, _, sub = line.partition("\t")
            if meta.split()[0] != "160000":
                continue
            path = (top / sub).resolve()
            if not (path / ".git").exists():
                raise VaultError(f"submodule {sub} of {name} is not checked out, so its code would be missing. "
                                 f"Run: git -C {top} submodule update --init --recursive")
            entry = (path, f"{name}--{sub.replace('/', '-')}", os.path.relpath(path, root).replace(os.sep, "/"))
            out.append(entry)
            queue.append(entry)
    return out


# ---------------------------------------------------------------- files, environment, hardware

def walk_files(paths: list[str], cwd: Path, root: Path, blobs: dict[str, Path] | None, what: str,
               since: float | None = None, stale: list[str] | None = None) -> list[dict]:
    """The files under paths, hashed into blobs. With since, files last written before it are left
    out and listed in stale: an output folder can hold files an earlier run wrote."""
    out = []
    for raw in paths:
        p = (cwd / raw).resolve() if not os.path.isabs(raw) else Path(raw).resolve()
        if not p.exists():
            raise VaultError(f"{what} {raw} does not exist")
        logical = Path(os.path.abspath(cwd / raw))
        try:
            logical.relative_to(root)
        except ValueError:
            raise VaultError(f"{what} {raw} is outside {root}. Put it (or a symlink to it) inside the "
                             f"repository, git-ignored if it is large, so its path is the same on every replay.")
        files = [logical] if not logical.is_dir() else sorted(
            Path(dp) / fn for dp, _, fns in os.walk(logical, followlinks=True) for fn in fns)
        for f in files:
            if not f.is_file():
                continue
            if since is not None and f.stat().st_mtime < since:
                if stale is not None:
                    stale.append(f.relative_to(root).as_posix())
                continue
            if blobs is None:
                # A check only: count, do not hash.
                out.append({"path": f.relative_to(root).as_posix(), "size": f.stat().st_size})
                continue
            hexd, size = sha256_file(f)
            blobs[hexd] = f
            out.append({"path": f.relative_to(root).as_posix(), "sha256": hexd, "size": size})
    return sorted({e["path"]: e for e in out}.values(), key=lambda e: e["path"])


INTERPRETER_PROBE = (
    "import json, platform, sys;"
    "print(json.dumps({'version': platform.python_version(), 'implementation': platform.python_implementation(),"
    "'executable': sys.executable, 'prefix': sys.prefix, 'platform': platform.platform(),"
    "'machine': platform.machine()}))"
)


def capture_environment(python: str, vendor: bool, work: Path, blobs: dict[str, Path], strict: bool) -> dict:
    env: dict[str, Any] = {}
    p = run_cmd([python, "-c", INTERPRETER_PROBE], check=False)
    if p.returncode == 0:
        env["python"] = json.loads(p.stdout)
    else:
        env["python"] = {"error": p.stderr.strip()[:300]}
    freeze = run_cmd([python, "-m", "pip", "freeze", "--all"], check=False)
    if freeze.returncode != 0 and shutil.which("uv"):
        freeze = run_cmd(["uv", "pip", "freeze", "--python", python], check=False)
    if freeze.returncode != 0:
        msg = f"could not list the packages of {python}: {freeze.stderr.strip()[:200]}"
        if strict:
            raise VaultError(msg)
        print(f"warning: {msg}", file=sys.stderr)
    else:
        lock = work / "requirements.lock"
        lock.write_text(freeze.stdout, encoding="utf-8")
        hexd, size = sha256_file(lock)
        blobs[hexd] = lock
        lines = [l.strip() for l in freeze.stdout.splitlines() if l.strip() and not l.startswith("#")]
        env["lock"] = {"sha256": hexd, "size": size, "packages": len(lines)}
        local = [l for l in lines if l.startswith("-e ") or " @ file:" in l]
        if local:
            env["unpinnable"] = local
            print(f"warning: {len(local)} package(s) are installed from a local path or in editable mode and "
                  f"cannot be fetched again by version: {', '.join(local[:3])}", file=sys.stderr)
        if vendor:
            env["wheels"] = vendor_wheels(python, lines, work, blobs, strict)
    if os.environ.get("CONDA_PREFIX") and shutil.which("conda"):
        p = run_cmd(["conda", "env", "export", "--no-builds"], check=False)
        if p.returncode == 0:
            f = work / "conda-environment.yml"
            f.write_text(p.stdout, encoding="utf-8")
            hexd, size = sha256_file(f)
            blobs[hexd] = f
            env["conda"] = {"sha256": hexd, "size": size}
    env["hardware"] = hardware()
    return env


def vendor_wheels(python: str, lines: list[str], work: Path, blobs: dict[str, Path], strict: bool) -> list[dict]:
    reqs = [l for l in lines if not l.startswith("-e ") and " @ " not in l]
    req_file = work / "vendor-requirements.txt"
    req_file.write_text("\n".join(reqs) + "\n", encoding="utf-8")
    dest = work / "wheels"
    dest.mkdir(exist_ok=True)
    p = run_cmd([python, "-m", "pip", "download", "--no-deps", "--disable-pip-version-check", "-q",
                 "-r", str(req_file), "-d", str(dest)], check=False)
    if p.returncode != 0:
        msg = f"pip download could not fetch every package: {p.stderr.strip()[-300:]}"
        if strict:
            raise VaultError(msg)
        print(f"warning: {msg}", file=sys.stderr)
    out = []
    for f in sorted(dest.iterdir()):
        hexd, size = sha256_file(f)
        blobs[hexd] = f
        out.append({"file": f.name, "sha256": hexd, "size": size})
    return out


def hardware() -> dict:
    hw: dict[str, Any] = {"cpu": platform.processor() or platform.machine(), "cores": os.cpu_count()}
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    hw["cpu"] = line.split(":", 1)[1].strip()
                    break
        with open("/proc/meminfo", encoding="utf-8") as f:
            hw["memory_kb"] = int(f.readline().split()[1])
    except OSError:
        pass
    if shutil.which("nvidia-smi"):
        p = run_cmd(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], check=False)
        if p.returncode == 0:
            hw["gpus"] = [l.strip() for l in p.stdout.splitlines() if l.strip()]
    return hw


def recorded_env(names: list[str]) -> dict[str, str]:
    out = {}
    for n in names:
        if SECRET_HINT.search(n):
            raise VaultError(f"{n} looks like a secret; a capsule is kept for years, so it is not recorded. "
                             f"Pass secrets to the experiment some other way.")
        if n in os.environ:
            out[n] = os.environ[n]
    for n in RECORDED_ENV:
        if n in os.environ:
            out[n] = os.environ[n]
    return out


# ---------------------------------------------------------------- the DAG

def node_snapshot(settings: Settings, node_id: str) -> dict:
    snap: dict[str, Any] = {"id": node_id}
    if not settings.dag_path or not settings.dag_path.is_file():
        return snap
    text = settings.dag_path.read_text(encoding="utf-8")
    m = re.search(r"^# dag-store-commit: ([0-9a-f]{7,64})", text, re.M)
    if m:
        snap["dag_store_commit"] = m.group(1)
    try:
        dag = read_yaml(settings.dag_path) or {}
    except Exception:  # noqa: BLE001 - the snapshot is a convenience
        return snap
    for node in dag.get("nodes", []) if isinstance(dag, dict) else []:
        if isinstance(node, dict) and node.get("id") == node_id:
            keep = ("hypothesis", "status", "target_improvement", "target", "metric", "parent", "parents",
                    "work_item_id", "work_item")
            snap["snapshot"] = json.loads(json.dumps({k: node[k] for k in keep if k in node}, default=str))
            break
    else:
        print(f"warning: {node_id} is not in {settings.dag_path}", file=sys.stderr)
    return snap


def dag_update_tool() -> Path | None:
    env = os.environ.get("RESEARCH_DAG_BIN")
    candidates = [Path(env) / "dag_update.py"] if env else []
    here = Path(__file__).resolve().parent
    candidates.append(here.parent.parent / "research-dag" / "bin" / "dag_update.py")
    return next((c for c in candidates if c.is_file()), None)


def link_to_dag(settings: Settings, node_id: str, ref: dict) -> None:
    tool = dag_update_tool()
    if not settings.research_yaml or tool is None:
        print("note: no research.yaml with the research-dag skill beside this one; record the capsule on the "
              f"node yourself: {json.dumps(ref)}", file=sys.stderr)
        return
    value = json.dumps(ref, sort_keys=True)
    p = subprocess.run([sys.executable, str(tool), "--action", "append", "--node-id", node_id,
                        "--field", "capsules", "--value", value], cwd=settings.root,
                       capture_output=True, text=True)
    if p.returncode != 0:
        print(f"warning: could not record the capsule on {node_id}: {(p.stdout + p.stderr).strip()[:300]}",
              file=sys.stderr)
    else:
        print(f"Recorded on {node_id}: capsules += {ref['id']}")


# ---------------------------------------------------------------- capsules

def capsule_key(project: str, node: str, cid: str) -> str:
    return f"capsules/{project}/{node}/{cid}.json"


def check_node_id(node: str) -> str:
    if not NAME_RE.match(node):
        raise VaultError(f"node id {node!r} must be letters, digits, '.', '_' or '-'")
    return node


def write_capsule(backend: Backend, project: str, node: str, manifest: dict, blobs: dict[str, Path],
                  files: dict[str, Path] | None = None) -> dict:
    """Upload the blobs and bundles, then the manifest. Returns the reference the DAG records."""
    sent = backend.put_blobs(blobs) + (backend.put_files(files) if files else 0)
    data = canonical(manifest)
    digest = hashlib.sha256(data).hexdigest()
    stamp = manifest["created_at"].replace("-", "").replace(":", "")
    cid = f"{stamp}-{digest[:12]}"
    key = capsule_key(project, node, cid)
    if not backend.write_once(key, data):
        existing = backend.read(key)
        if existing is None or hashlib.sha256(existing).hexdigest() != digest:
            raise VaultError(f"{backend.url(key)} exists with different content; refusing to overwrite it")
    total = sum(e["size"] for e in iter_blob_refs(manifest))
    print(f"Capsule {node}/{cid}: {len({e['sha256'] for e in iter_blob_refs(manifest)})} files, "
          f"{human(total)}, {sent} new to the vault")
    print(f"  {backend.url(key)}")
    ref = {"id": cid, "sha256": digest, "uri": backend.url(key), "kind": manifest["kind"],
           "at": manifest["created_at"]}
    if manifest.get("comparison"):
        ref["verdict"] = manifest["comparison"]["verdict"]
    if manifest.get("result"):
        ref["result"] = manifest["result"]
    return ref


def iter_blob_refs(manifest: dict) -> Iterable[dict]:
    for repo in manifest.get("code", []):
        if repo.get("archive"):
            yield repo["archive"]
        if repo.get("patch"):
            yield repo["patch"]
        yield from repo.get("untracked", [])
    yield from manifest.get("data", [])
    env = manifest.get("environment", {})
    for k in ("lock", "conda"):
        if env.get(k):
            yield env[k]
    yield from env.get("wheels", [])
    run = manifest.get("run", {})
    for k in ("stdout", "stderr"):
        if run.get(k):
            yield run[k]
    yield from manifest.get("outputs", [])


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def resolve(backend: Backend, settings: Settings, ref: str, node: str | None = None) -> tuple[str, str, dict, str]:
    """(node, capsule id, manifest, digest) for a capsule id, node/id or manifest URI."""
    ref = ref.strip()
    m = re.search(r"capsules/([^/]+)/([^/]+)/([^/]+?)(?:\.json)?$", ref)
    if m:
        project, node, cid = m.groups()
    elif "/" in ref:
        node, cid = ref.rsplit("/", 1)
        project = settings.project
    else:
        cid, project = ref, settings.project
        if not CAPSULE_RE.match(cid):
            raise VaultError(f"{cid!r} is not a capsule id (<stamp>-<hash12>)")
        if not node:
            hits = [k for k in backend.list(f"capsules/{project}/") if k.endswith(f"/{cid}.json")]
            if not hits:
                raise VaultError(f"no capsule {cid} in project {project}")
            node = hits[0].split("/")[2]
    if not CAPSULE_RE.match(cid):
        raise VaultError(f"{cid!r} is not a capsule id (<stamp>-<hash12>)")
    data = backend.read(capsule_key(project, node, cid))
    if data is None:
        raise VaultError(f"capsule {node}/{cid} is not in {backend.uri} (project {project})")
    digest = hashlib.sha256(data).hexdigest()
    if digest[:12] != cid.rsplit("-", 1)[1]:
        raise VaultError(f"capsule {node}/{cid} is corrupt: its manifest hashes to {digest[:12]}")
    manifest = json.loads(data)
    if manifest.get("format") not in FORMATS:
        raise VaultError(f"capsule {node}/{cid} is {manifest.get('format')}, which this experiment-vault "
                         f"{TOOL_VERSION} cannot read; update the skill")
    return node, cid, manifest, digest


# ---------------------------------------------------------------- running

def tee_run(argv: list[str], cwd: Path, env: dict, work: Path) -> tuple[int, Path, Path, float]:
    out_path, err_path = work / "stdout.txt", work / "stderr.txt"
    start = time.monotonic()
    exe = shutil.which(argv[0], path=env.get("PATH")) or argv[0]
    try:
        proc = subprocess.Popen([exe, *argv[1:]], cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as e:
        raise VaultError(f"cannot run {argv[0]}: not found") from e

    def pump(src, dest_path, sink):
        with open(dest_path, "wb") as f:
            for chunk in iter(lambda: src.read1(65536) if hasattr(src, "read1") else src.read(65536), b""):
                f.write(chunk)
                sink.write(chunk)
                sink.flush()

    threads = [threading.Thread(target=pump, args=(proc.stdout, out_path, sys.stdout.buffer)),
               threading.Thread(target=pump, args=(proc.stderr, err_path, sys.stderr.buffer))]
    for t in threads:
        t.start()
    code = proc.wait()
    for t in threads:
        t.join()
    return code, out_path, err_path, round(time.monotonic() - start, 3)


def blob_entry(path: Path, blobs: dict[str, Path]) -> dict:
    hexd, size = sha256_file(path)
    blobs[hexd] = path
    return {"sha256": hexd, "size": size}


def load_metrics(path: Path | None) -> dict | None:
    if path is None:
        return None
    if not path.is_file():
        print(f"warning: metrics file {path} was not written", file=sys.stderr)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"warning: metrics file {path} is not JSON ({e})", file=sys.stderr)
        return None


def flatten(d: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(d, dict):
        out = {}
        for k, v in d.items():
            out.update(flatten(v, f"{prefix}{k}."))
        return out
    return {prefix.rstrip("."): d}


def compare(original: dict, metrics: dict | None, outputs: list[dict], exit_code: int,
            rtol: float, atol: float) -> dict:
    was = flatten(original.get("metrics") or {})
    now = flatten(metrics or {})
    rows, metric_ok = {}, True
    for k, v in was.items():
        n = now.get(k)
        if isinstance(v, (int, float)) and isinstance(n, (int, float)) and not isinstance(v, bool):
            ok = abs(n - v) <= atol + rtol * abs(v)
            rows[k] = {"was": v, "now": n, "delta": n - v, "ok": ok}
        else:
            ok = n == v
            rows[k] = {"was": v, "now": n, "ok": ok}
        metric_ok &= ok
    before = {o["path"]: o["sha256"] for o in original.get("outputs", [])}
    after = {o["path"]: o["sha256"] for o in outputs}
    changed = sorted(p for p in before if after.get(p) != before[p])
    identical = len(before) - len(changed)
    if exit_code != 0:
        verdict = "failed"
    elif metric_ok and not changed:
        verdict = "identical"
    elif metric_ok:
        verdict = "reproduced"
    else:
        verdict = "drifted"
    return {"verdict": verdict, "rtol": rtol, "atol": atol, "metrics": rows,
            "outputs": {"identical": identical, "changed": changed,
                        "new": sorted(p for p in after if p not in before)}}


def build_manifest(settings: Settings, args, node: str, kind: str, code: list[dict], data: list[dict],
                   environment: dict, run: dict, outputs: list[dict], metrics: dict | None) -> dict:
    manifest: dict[str, Any] = {
        "format": FORMAT, "tool": f"experiment-vault {TOOL_VERSION}", "kind": kind,
        "created_at": iso(now_utc()), "host": socket.gethostname(), "project": settings.project,
        "node": node_snapshot(settings, node), "code": code, "data": data, "environment": environment,
        "run": run, "outputs": outputs, "metrics": metrics,
        "tolerance": {"rtol": args.rtol if args.rtol is not None else settings.rtol,
                      "atol": args.atol if args.atol is not None else settings.atol},
    }
    if getattr(args, "agent", None):
        manifest["agent"] = args.agent
    if getattr(args, "note", None):
        manifest["note"] = args.note
    if getattr(args, "work_item", None):
        manifest["work_item"] = args.work_item
    if getattr(args, "metric", None) and metrics is not None:
        value = flatten(metrics).get(args.metric)
        result = {"metric": args.metric, "value": value}
        target = getattr(args, "target", None)
        if target is None:
            snap = manifest["node"].get("snapshot") or {}
            target = snap.get("target_improvement", snap.get("target"))
        if target is not None:
            result["target"] = target
        manifest["result"] = result
    return manifest


def cmd_preflight(settings: Settings, args, observed: bool) -> int:
    """Check a run or capture could be kept, changing nothing: no tag, no upload, no run."""
    problems: list[str] = []
    notes: list[str] = []

    def check(fn):
        try:
            return fn()
        except VaultError as e:
            problems.append(str(e))
            return None

    backend = None
    if check(settings.need) is None and not problems:
        backend = check(lambda: open_backend(settings.uri))
        if backend is not None and check(lambda: backend.read("VAULT.md")) is None and not problems:
            problems.append(f"{settings.uri} has no VAULT.md: it is not initialised, or not reachable. Run vault.py init")
    check(lambda: check_node_id(args.node))
    argv = args.command if observed else (args.cmd_argv or [])
    if not argv:
        problems.append("no command: give it after --" if observed else "no command: pass --cmd")
    cwd = Path(args.cwd).resolve()
    top = check(lambda: git(["rev-parse", "--show-toplevel"], cwd))
    if top is None:
        problems.append(f"{cwd} is not in a git repository")
    else:
        root = Path(top).resolve()
        storage = args.code_storage or settings.code_storage
        for path, name, rel in check(lambda: repos_to_capture(root, args.repo or [])) or []:
            e = check(lambda: capture_repo(path, name, args.allow_dirty, Path("."), {}, settings.managed,
                                           backend=backend, storage=storage, dry=True))
            if e:
                extra = f", {e['new_commits']} commit(s) new to the vault" if "new_commits" in e else ""
                notes.append(f"code {name}{' at ' + rel if rel else ''}: {e['commit'][:12]} as {e['storage']}{extra}"
                             f"{'' if e.get('pushed', True) else '; the commit is on no remote branch'}")
        n, size = 0, 0
        for d in args.data or []:
            files = check(lambda: walk_files([d], cwd, root, None, "data"))
            for f in files or []:
                n, size = n + 1, size + f["size"]
        notes.append(f"data: {n} files, {human(size)}")
        for what, paths in (("output", args.outputs or []), ("metrics", [args.metrics] if args.metrics else [])):
            for o in paths:
                logical = Path(os.path.abspath(cwd / o))
                if not logical.is_relative_to(root):
                    problems.append(f"{what} {o} is outside {root}")
        if not args.metrics:
            notes.append("no --metrics: a replay can compare output files only")
    check(lambda: recorded_env(args.env or []))
    if "PYTHONHASHSEED" not in os.environ:
        notes.append("PYTHONHASHSEED is not set; set it for bit-identical replays")
    py = args.python or sys.executable
    if run_cmd([py, "-m", "pip", "--version"], check=False).returncode != 0 and not shutil.which("uv"):
        problems.append(f"{py} has no pip (and uv is not installed), so its packages cannot be recorded")
    for line in notes:
        print(f"  {line}")
    for line in problems:
        print(f"PROBLEM {line}")
    print("ready: nothing was run, tagged or uploaded" if not problems else f"not ready: {len(problems)} problem(s)")
    return 0 if not problems else 2


def cmd_run(settings: Settings, args, observed: bool) -> int:
    if args.dry_run:
        return cmd_preflight(settings, args, observed)
    settings.need()
    node = check_node_id(args.node)
    backend = open_backend(settings.uri)
    cwd = Path(args.cwd).resolve()
    root = Path(git(["rev-parse", "--show-toplevel"], cwd)).resolve()
    argv = args.command if observed else (args.cmd_argv or [])
    if observed and not argv:
        raise VaultError("give the command after --, for example: vault.py run --node H-001 -- python train.py")
    prior = None
    if args.retest_of:
        _, prior_id, prior, _ = resolve(backend, settings, args.retest_of, node)
    with tempfile.TemporaryDirectory(prefix="vault-") as td:
        work = Path(td)
        blobs: dict[str, Path] = {}
        files: dict[str, Path] = {}
        storage = args.code_storage or settings.code_storage
        pin = dict(backend=backend, files=files, storage=storage, push_tag=not args.no_push_tag)
        code = []
        for path, name, rel in repos_to_capture(root, args.repo or []):
            code.append(capture_repo(path, (args.name or name) if rel is None else name, args.allow_dirty,
                                     work, blobs, settings.managed, **pin))
            if rel is not None:
                code[-1]["path"] = rel
        data = walk_files(args.data or [], cwd, root, blobs, "data")
        env_vars = recorded_env(args.env or [])
        if "PYTHONHASHSEED" not in env_vars:
            print("note: PYTHONHASHSEED is not set, so set and dict-of-str iteration order can differ "
                  "between runs; set it for bit-identical replays", file=sys.stderr)
        seeds = dict(s.split("=", 1) for s in (args.seed or []))
        run: dict[str, Any] = {"argv": argv, "cwd": cwd.relative_to(root).as_posix() or ".",
                               "env": env_vars, "seeds": seeds, "observed": observed}
        started = now_utc()
        started_wall = time.time() - 0.001
        if observed:
            code_rc, out_p, err_p, secs = tee_run(argv, cwd, without_vault_keys(os.environ), work)
            run.update({"started_at": iso(started), "duration_s": secs, "exit_code": code_rc,
                        "stdout": blob_entry(out_p, blobs), "stderr": blob_entry(err_p, blobs)})
        else:
            code_rc = args.exit_code
            run["exit_code"] = code_rc
            for k in ("stdout", "stderr"):
                if getattr(args, k):
                    run[k] = blob_entry(Path(getattr(args, k)).resolve(), blobs)
        environment = capture_environment(args.python or sys.executable,
                                          args.vendor_wheels or settings.vendor_wheels, work, blobs, args.strict)
        stale: list[str] = []
        outputs = walk_files([o for o in (args.outputs or []) if (cwd / o).exists()], cwd, root, blobs, "output",
                             since=started_wall if observed else None, stale=stale)
        if stale:
            print(f"warning: {len(stale)} file(s) under --outputs were not written by this run and are not kept "
                  f"as its outputs: {', '.join(stale[:5])}. Empty output folders before a run.", file=sys.stderr)
        for o in args.outputs or []:
            if not (cwd / o).exists():
                print(f"warning: output {o} was not written", file=sys.stderr)
        metrics = load_metrics((cwd / args.metrics) if args.metrics else None)
        if args.metrics:
            run["metrics_path"] = Path(os.path.abspath(cwd / args.metrics)).relative_to(root).as_posix()
        manifest = build_manifest(settings, args, node, "retest" if prior else "run", code, data,
                                  environment, run, outputs, metrics)
        if prior:
            tol = manifest["tolerance"]
            manifest["retest_of"] = f"{node}/{prior_id}"
            manifest["comparison"] = compare(prior, metrics, outputs, code_rc, tol["rtol"], tol["atol"])
        ref = write_capsule(backend, settings.project, node, manifest, blobs, files)
    if prior:
        print_comparison(manifest["comparison"])
    if not args.no_link:
        link_to_dag(settings, node, ref)
    if code_rc == 0 and prior and manifest["comparison"]["verdict"] == "drifted":
        return 3
    return code_rc


# ---------------------------------------------------------------- restore and replay

def safe_extract(tar_path: Path, dest: Path) -> None:
    with tarfile.open(tar_path) as tf:
        if hasattr(tarfile, "data_filter"):
            tf.extractall(dest, filter="tar")
            return
        for m in tf.getmembers():
            target = (dest / m.name).resolve()
            if not str(target).startswith(str(dest.resolve())) or m.islnk():
                raise VaultError(f"refusing to extract {m.name} outside {dest}")
        tf.extractall(dest)  # noqa: S202 - members checked above


def place(src: Path, dest: Path, mode: int | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    if mode is not None:
        os.chmod(dest, mode)


def restore(backend: Backend, manifest: dict, dest: Path) -> Path:
    """Materialise the capsule under dest. Returns the run directory."""
    if dest.exists() and any(dest.iterdir()):
        raise VaultError(f"{dest} is not empty")
    dest.mkdir(parents=True, exist_ok=True)
    cache = dest / ".vault" / "blobs"
    hexes = [e["sha256"] for e in iter_blob_refs(manifest)]
    backend.get_blobs(hexes, cache)
    for hexd in set(hexes):
        got, _ = sha256_file(cache / hexd)
        if got != hexd:
            raise VaultError(f"blob {hexd} is corrupt in {backend.uri}: it hashes to {got}")
    code = manifest["code"]
    main = dest / "repos" / code[0]["name"]
    for repo in code:
        target = dest / "repos" / repo["name"]
        if repo.get("path"):
            beside = (main / repo["path"]).resolve()
            if beside != main.resolve() and beside.is_relative_to(dest.resolve()):
                target = beside
        target.mkdir(parents=True, exist_ok=True)
        if repo.get("bundles"):
            restore_bundled(backend, repo, target, dest / ".vault")
        else:
            safe_extract(cache / repo["archive"]["sha256"], target)
        if repo.get("patch"):
            run_cmd(["git", "apply", "--binary", str(cache / repo["patch"]["sha256"])], cwd=target)
        for u in repo.get("untracked", []):
            place(cache / u["sha256"], target / u["path"])
    for d in manifest.get("data", []):
        place(cache / d["sha256"], main / d["path"])
    env = manifest.get("environment", {})
    if env.get("lock"):
        place(cache / env["lock"]["sha256"], dest / "env" / "requirements.lock")
    for w in env.get("wheels", []):
        place(cache / w["sha256"], dest / "env" / "wheels" / w["file"])
    for o in manifest.get("outputs", []):
        place(cache / o["sha256"], dest / "original-outputs" / o["path"])
    (dest / "CAPSULE.json").write_bytes(canonical(manifest))
    shutil.rmtree(dest / ".vault")
    run_dir = main / manifest["run"].get("cwd", ".")
    write_replay_scripts(dest, manifest, run_dir)
    return run_dir


def is_python(arg: str) -> bool:
    return os.path.basename(arg).lower() in PYTHON_NAMES


def write_replay_scripts(dest: Path, manifest: dict, run_dir: Path) -> None:
    rel = os.path.relpath(run_dir, dest).replace(os.sep, "/")
    argv = manifest["run"]["argv"]
    env = manifest["run"].get("env", {})
    has_wheels = bool(manifest.get("environment", {}).get("wheels"))
    pip_src = "--no-index --find-links env/wheels " if has_wheels else ""
    venv_py = "../" * (rel.count("/") + 1) + ".venv/bin/python"
    sh = ["#!/usr/bin/env bash", "# Replays the capsule by hand. vault.py replay does this and compares the result.",
          "set -euo pipefail", 'cd "$(dirname "$0")"', "python -m venv .venv",
          f".venv/bin/python -m pip install {pip_src}-r env/requirements.lock",
          *[f"export {k}={json.dumps(v)}" for k, v in env.items()], f"cd {rel}",
          " ".join(venv_py if i == 0 and is_python(a) else json.dumps(a) for i, a in enumerate(argv))]
    (dest / "replay.sh").write_text("\n".join(sh) + "\n", encoding="utf-8", newline="\n")
    up = "..\\" * (rel.count("/") + 1)
    ps = ["# Replays the capsule by hand. vault.py replay does this and compares the result.",
          "$ErrorActionPreference = 'Stop'", "Set-Location $PSScriptRoot", "python -m venv .venv",
          f".venv\\Scripts\\python.exe -m pip install {pip_src}-r env\\requirements.lock",
          *[f"$env:{k} = '{v}'" for k, v in env.items()], f"Set-Location '{rel}'",
          "& " + " ".join(f"'{a}'" if i else (f"'{up}.venv\\Scripts\\python.exe'" if is_python(a) else f"'{a}'")
                          for i, a in enumerate(argv))]
    (dest / "replay.ps1").write_text("\r\n".join(ps) + "\r\n", encoding="utf-8")


def setup_venv(dest: Path, manifest: dict, python: str, pip_extra: list[str]) -> str:
    venv = dest / ".venv"
    run_cmd([python, "-m", "venv", str(venv)])
    py = str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    lock = dest / "env" / "requirements.lock"
    if lock.is_file():
        lines = [l for l in lock.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("-e ") and " @ " not in l
                 and not re.match(r"^(pip|setuptools|wheel)==", l)]
        reqs = dest / "env" / "install.txt"
        reqs.write_text("\n".join(lines) + "\n", encoding="utf-8")
        wheels = dest / "env" / "wheels"
        base = [py, "-m", "pip", "install", "--disable-pip-version-check", "-q"]
        if wheels.is_dir():
            print(f"Installing {len(lines)} pinned packages from the vendored wheels...")
            p = run_cmd([*base, "--no-index", "--find-links", str(wheels), "-r", str(reqs)], check=False)
            if p.returncode != 0:
                print("warning: the vendored wheels do not install here (another platform or Python?); "
                      "installing the same pinned versions from the package index, preferring the wheels",
                      file=sys.stderr)
                run_cmd([*base, "--find-links", str(wheels), "-r", str(reqs)])
        else:
            print(f"Installing {len(lines)} pinned packages from the package index...")
            run_cmd([*base, "-r", str(reqs)])
    if pip_extra:
        print(f"Installing overrides: {' '.join(pip_extra)}")
        run_cmd([py, "-m", "pip", "install", "--disable-pip-version-check", "-q", *pip_extra])
    return py


def cmd_replay(settings: Settings, args) -> int:
    settings.need()
    backend = open_backend(settings.uri)
    if args.pip and args.setup != "venv":
        raise VaultError("--pip needs --setup venv, so the overrides do not change your own environment")
    node, cid, manifest, _ = resolve(backend, settings, args.capsule, args.node)
    if args.to:
        dest = Path(args.to).resolve()
    else:
        dest = (Path.cwd() / ".vault-replay" / cid).resolve()
        n = 2
        while dest.exists() and any(dest.iterdir()):
            dest = (Path.cwd() / ".vault-replay" / f"{cid}-{n}").resolve()
            n += 1
    run_dir = restore(backend, manifest, dest)
    print(f"Restored {node}/{cid} into {dest}")
    recorded_py = (manifest.get("environment", {}).get("python") or {})
    base_python = args.python or sys.executable
    if args.setup == "venv":
        py = setup_venv(dest, manifest, base_python, args.pip or [])
    else:
        py = base_python
    probe = json.loads(run_cmd([py, "-c", INTERPRETER_PROBE]).stdout)
    if recorded_py.get("version") and probe["version"] != recorded_py["version"]:
        print(f"warning: Python {probe['version']} replays a run made with {recorded_py['version']}", file=sys.stderr)
    run = manifest["run"]
    argv = list(run["argv"])
    if argv and (is_python(argv[0]) or argv[0] == recorded_py.get("executable")):
        argv[0] = py
    env = without_vault_keys(os.environ)
    env.update(run.get("env", {}))
    if args.setup == "venv":
        env["VIRTUAL_ENV"] = str(dest / ".venv")
        env["PATH"] = str(Path(py).parent) + os.pathsep + env.get("PATH", "")
    with tempfile.TemporaryDirectory(prefix="vault-") as td:
        work = Path(td)
        blobs: dict[str, Path] = {}
        rc, out_p, err_p, secs = tee_run(argv, run_dir, env, work)
        main = dest / "repos" / manifest["code"][0]["name"]
        out_paths = [o["path"] for o in manifest.get("outputs", [])]
        outputs = []
        for p in out_paths:
            f = main / p
            if f.is_file():
                outputs.append({"path": p, **blob_entry(f, blobs)})
        metrics_rel = run.get("metrics_path")
        metrics = load_metrics(main / metrics_rel) if metrics_rel else None
        tol = manifest.get("tolerance", {})
        rtol = args.rtol if args.rtol is not None else tol.get("rtol", settings.rtol)
        atol = args.atol if args.atol is not None else tol.get("atol", settings.atol)
        comparison = compare(manifest, metrics, outputs, rc, rtol, atol)
        print_comparison(comparison)
        if not args.no_record:
            environment = capture_environment(py, False, work, blobs, False)
            new_run = {**run, "argv": run["argv"], "observed": True, "started_at": iso(now_utc()),
                       "duration_s": secs, "exit_code": rc,
                       "stdout": blob_entry(out_p, blobs), "stderr": blob_entry(err_p, blobs),
                       "replay": {"setup": args.setup, "pip": args.pip or []}}
            args.metric = (manifest.get("result") or {}).get("metric")
            args.target = (manifest.get("result") or {}).get("target")
            retest = build_manifest(settings, args, node, "retest", manifest["code"], manifest.get("data", []),
                                    environment, new_run, outputs, metrics)
            retest["tolerance"] = {"rtol": rtol, "atol": atol}
            retest["retest_of"] = f"{node}/{cid}"
            retest["comparison"] = comparison
            ref = write_capsule(backend, settings.project, node, retest, blobs)
            if not args.no_link:
                link_to_dag(settings, node, ref)
    return {"identical": 0, "reproduced": 0, "drifted": 3}.get(comparison["verdict"], 1)


def print_comparison(c: dict) -> None:
    print(f"Verdict: {c['verdict']} (rtol {c['rtol']}, atol {c['atol']})")
    for k, row in c["metrics"].items():
        mark = "ok " if row["ok"] else "DIFF"
        delta = f" (delta {row['delta']:+.6g})" if "delta" in row else ""
        print(f"  {mark} {k}: was {row['was']}, now {row['now']}{delta}")
    o = c["outputs"]
    print(f"  outputs: {o['identical']} identical, {len(o['changed'])} changed"
          + (f": {', '.join(o['changed'][:5])}" if o["changed"] else ""))


# ---------------------------------------------------------------- reading

def cmd_list(settings: Settings, args) -> int:
    settings.need()
    backend = open_backend(settings.uri)
    prefix = f"capsules/{settings.project}/" + (f"{check_node_id(args.node)}/" if args.node else "")
    keys = [k for k in backend.list(prefix) if k.endswith(".json")]
    if not keys:
        print(f"No capsules under {backend.url(prefix)}")
        return 0
    for k in keys:
        _, _, node, name = k.split("/", 3)
        line = f"{node}/{name[:-5]}"
        if args.long:
            m = json.loads(backend.read(k) or b"{}")
            verdict = (m.get("comparison") or {}).get("verdict", "")
            res = m.get("result") or {}
            line += f"  {m.get('kind', '?'):6} exit {m.get('run', {}).get('exit_code')}"
            if res:
                line += f"  {res.get('metric')}={res.get('value')}"
            if verdict:
                line += f"  {verdict}"
            if m.get("note"):
                line += f"  {m['note'][:60]}"
        print(line)
    return 0


def cmd_show(settings: Settings, args) -> int:
    settings.need()
    backend = open_backend(settings.uri)
    node, cid, m, digest = resolve(backend, settings, args.capsule, args.node)
    if args.json:
        sys.stdout.write(canonical(m).decode("utf-8"))
        return 0
    print(f"{node}/{cid}  {m['kind']}  {m['created_at']}  on {m.get('host')}  sha256 {digest}")
    snap = m.get("node", {}).get("snapshot") or {}
    if snap.get("hypothesis"):
        print(f"  hypothesis: {snap['hypothesis']}")
    for r in m["code"]:
        print(f"  code {r['name']}: {r.get('remote', '(no remote)')} @ {r['commit'][:12]}"
              f"{' as git bundles, tag ' + r['tag'] if r.get('bundles') else ' as a snapshot'}"
              f"{' (dirty, patch stored)' if r.get('dirty') else ''}{'' if r.get('exact') else ' (archive not exact)'}"
              f"{'' if r.get('pushed', True) else ' (commit not on any remote branch)'}")
    print(f"  data: {len(m.get('data', []))} files, {human(sum(d['size'] for d in m.get('data', [])))}")
    env = m.get("environment", {})
    py = env.get("python", {})
    print(f"  python {py.get('version')} on {py.get('platform')}; {env.get('lock', {}).get('packages', 0)} packages"
          f"{', wheels vendored' if env.get('wheels') else ''}")
    run = m["run"]
    print(f"  run: {' '.join(run['argv'])}  (in {run.get('cwd')}, exit {run.get('exit_code')})")
    if run.get("seeds"):
        print(f"  seeds: {run['seeds']}")
    print(f"  outputs: {len(m.get('outputs', []))} files")
    if m.get("result"):
        print(f"  result: {m['result']}")
    if m.get("comparison"):
        print(f"  retest of {m.get('retest_of')}:")
        print_comparison(m["comparison"])
    return 0


def cmd_verify(settings: Settings, args) -> int:
    settings.need()
    backend = open_backend(settings.uri)
    if args.capsule:
        targets = [args.capsule if "/" in args.capsule or not args.node else f"{args.node}/{args.capsule}"]
    else:
        if not (args.node or args.all):
            raise VaultError("name a capsule, or pass --node or --all")
        prefix = f"capsules/{settings.project}/" + (f"{check_node_id(args.node)}/" if args.node else "")
        targets = [k for k in backend.list(prefix) if k.endswith(".json")]
    if args.sha256 and len(targets) != 1:
        raise VaultError("--sha256 checks one capsule; name it")
    bad = 0
    for t in targets:
        try:
            node, cid, m, digest = resolve(backend, settings, t)
            if args.sha256 and digest != args.sha256:
                raise VaultError(f"manifest hash {digest} is not the {args.sha256} the DAG records")
            hexes = {e["sha256"] for e in iter_blob_refs(m)}
            missing = backend.missing_blobs(hexes)
            if missing:
                raise VaultError(f"{len(missing)} of {len(hexes)} blobs missing: {', '.join(missing[:3])}")
            bundles = set(iter_bundle_keys(m))
            gone = backend.missing(bundles)
            if gone:
                raise VaultError(f"{len(gone)} of {len(bundles)} code bundles missing: {', '.join(gone[:3])}")
            if args.deep:
                with tempfile.TemporaryDirectory() as td:
                    backend.get_blobs(hexes, Path(td))
                    for h in hexes:
                        if sha256_file(Path(td) / h)[0] != h:
                            raise VaultError(f"blob {h} is corrupt")
                    for repo in m.get("code", []):
                        if repo.get("bundles"):
                            restore_bundled(backend, repo, Path(td) / "repos" / repo["name"], Path(td))
            what = f"{len(hexes)} blobs" + (f" and {len(bundles)} code bundles" if bundles else "")
            print(f"ok   {node}/{cid}: {what}{' re-hashed, code rebuilt and its tree checked' if args.deep else ' present'}")
        except VaultError as e:
            bad += 1
            print(f"FAIL {t}: {e}")
    return 1 if bad else 0


RESULT_STATUSES = ("validated", "ineffective", "contested", "completed", "tested", "partially_tested")


def cmd_coverage(settings: Settings, args) -> int:
    """Which result nodes have a capsule, and (with --verify) whether each capsule is intact."""
    if not settings.dag_path or not settings.dag_path.is_file():
        raise VaultError("coverage reads the DAG at research.yaml's dag_path, and there is none here")
    dag = read_yaml(settings.dag_path) or {}
    nodes = [n for n in dag.get("nodes", []) if isinstance(n, dict) and n.get("status") in RESULT_STATUSES]
    without = [n["id"] for n in nodes if not n.get("capsules")]
    print(f"{len(nodes) - len(without)} of {len(nodes)} result nodes have a capsule")
    for nid in without:
        print(f"  no capsule: {nid} ({next(n['status'] for n in nodes if n['id'] == nid)})")
    bad = 0
    if args.verify:
        settings.need()
        backend = open_backend(settings.uri)
        for n in nodes:
            for c in n.get("capsules") or []:
                cid = c.get("id") if isinstance(c, dict) else str(c)
                try:
                    _, _, m, digest = resolve(backend, settings, f"{n['id']}/{cid}")
                    if isinstance(c, dict) and c.get("sha256") and c["sha256"] != digest:
                        raise VaultError(f"manifest hash {digest[:12]} is not the {c['sha256'][:12]} the DAG records")
                    missing = backend.missing_blobs({e["sha256"] for e in iter_blob_refs(m)})
                    missing += backend.missing(set(iter_bundle_keys(m)))
                    if missing:
                        raise VaultError(f"{len(missing)} files missing")
                except VaultError as e:
                    bad += 1
                    print(f"  FAIL {n['id']}/{cid}: {e}")
        print(f"{'every recorded capsule is intact' if not bad else f'{bad} capsule(s) failed'}")
    return 1 if bad or (args.strict and without) else 0


def cmd_init(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    wrote = backend.write_once("VAULT.md", VAULT_README.encode("utf-8"))
    print(f"{'Initialised' if wrote else 'Already initialised:'} {backend.uri}")
    if settings.uri.startswith("gs://"):
        print("Storage classes: run `vault.py lifecycle` for the bucket settings that move old capsules to Archive.")
    return 0


def cmd_lifecycle(settings: Settings, args) -> int:
    rules = {"rule": [
        {"action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
         "condition": {"age": args.nearline, "matchesStorageClass": ["STANDARD"]}},
        {"action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
         "condition": {"age": args.coldline, "matchesStorageClass": ["NEARLINE"]}},
        {"action": {"type": "SetStorageClass", "storageClass": "ARCHIVE"},
         "condition": {"age": args.archive, "matchesStorageClass": ["COLDLINE"]}},
    ]}
    print(json.dumps(rules, indent=2))
    return 0


# ---------------------------------------------------------------- command line

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vault.py", description="Keep every hypothesis experiment as a "
                                 "reproducible capsule in an experiment vault, and replay it.")
    ap.add_argument("--vault", help="The vault: a folder, file://, or gs://bucket/prefix")
    ap.add_argument("--project", help="The project's folder in the vault (default: vault.project or dag_project)")
    sub = ap.add_subparsers(dest="command_name", required=True)

    def capture_opts(p):
        p.add_argument("--node", required=True, help="The hypothesis node id the capsule belongs to")
        p.add_argument("--cwd", default=".", help="Where the command runs (default: here); must be in a git repository")
        p.add_argument("--name", help="Name for the main repository (default: its folder name)")
        p.add_argument("--repo", action="append", help="Another git repository the run used (repeatable)")
        p.add_argument("--data", action="append", help="A file or folder the run reads, inside the repository (repeatable)")
        p.add_argument("--outputs", action="append", help="A file or folder the run writes (repeatable)")
        p.add_argument("--metrics", help="The JSON file of metrics the run writes")
        p.add_argument("--metric", help="The metric (dotted key in --metrics) that is the node's result")
        p.add_argument("--target", type=float, help="The target (default: the node's target in the DAG)")
        p.add_argument("--seed", action="append", help="A seed the run uses, name=value (repeatable)")
        p.add_argument("--env", action="append", help="An environment variable that affects the result (repeatable)")
        p.add_argument("--python", help="The interpreter the experiment uses (default: this one)")
        p.add_argument("--vendor-wheels", action="store_true", help="Store the wheels of every pinned package too")
        p.add_argument("--allow-dirty", action="store_true", help="Allow uncommitted changes, stored as a patch")
        p.add_argument("--code-storage", choices=["bundle", "archive"],
                       help="bundle: tag the commit and keep incremental git bundles (default); "
                            "archive: a compressed snapshot of the commit")
        p.add_argument("--no-push-tag", action="store_true", help="Tag the commit locally only, without pushing the tag")
        p.add_argument("--strict", action="store_true", help="Fail when the environment cannot be fully captured")
        p.add_argument("--rtol", type=float, help="Relative tolerance a replay's metrics must meet")
        p.add_argument("--atol", type=float, help="Absolute tolerance a replay's metrics must meet")
        p.add_argument("--retest-of", help="A capsule this run retests; the result is compared with it")
        p.add_argument("--note", help="Why this run was made")
        p.add_argument("--agent", help="Who ran it: an agent handle or a person")
        p.add_argument("--work-item", help="The work item the run belongs to")
        p.add_argument("--no-link", action="store_true", help="Do not record the capsule on the DAG node")
        p.add_argument("--dry-run", action="store_true",
                       help="Check everything the capture needs and print the plan; run, tag and upload nothing")

    p = sub.add_parser("init", help="Write VAULT.md at the vault root")
    p = sub.add_parser("run", help="Run a command and keep everything it used and produced as a capsule")
    capture_opts(p)
    p.add_argument("command", nargs=argparse.REMAINDER, help="-- then the command")
    p = sub.add_parser("capture", help="Keep a run that already happened as a capsule")
    capture_opts(p)
    p.add_argument("--cmd", required=True, help="The command the outputs came from, as one string")
    p.add_argument("--exit-code", type=int, default=0)
    p.add_argument("--stdout", help="A file holding the run's console output")
    p.add_argument("--stderr", help="A file holding the run's error output")
    p = sub.add_parser("list", help="List capsules")
    p.add_argument("--node")
    p.add_argument("--long", action="store_true", help="Read each manifest for its kind, result and verdict")
    p = sub.add_parser("show", help="Summarise one capsule")
    p.add_argument("capsule")
    p.add_argument("--node")
    p.add_argument("--json", action="store_true", help="Print the manifest")
    p = sub.add_parser("verify", help="Check capsules are intact: manifest hash and every blob present")
    p.add_argument("capsule", nargs="?")
    p.add_argument("--node")
    p.add_argument("--all", action="store_true")
    p.add_argument("--sha256", help="The manifest hash the DAG records, to check against")
    p.add_argument("--deep", action="store_true", help="Download and re-hash every blob")
    p = sub.add_parser("restore", help="Materialise a capsule into a folder")
    p.add_argument("capsule")
    p.add_argument("--node")
    p.add_argument("--to", required=True)
    p = sub.add_parser("replay", help="Restore a capsule, run it again, and compare")
    p.add_argument("capsule")
    p.add_argument("--node")
    p.add_argument("--to", help="Where to restore (default: .vault-replay/<capsule id>)")
    p.add_argument("--setup", choices=["venv", "none"], default="venv",
                   help="venv: a fresh virtual environment from the capsule's lock (default); "
                        "none: this interpreter as it is, to retest against what has changed")
    p.add_argument("--python", help="The base interpreter (default: this one)")
    p.add_argument("--pip", action="append", help="A requirement to install over the lock, e.g. numpy==2.1.0 (repeatable)")
    p.add_argument("--rtol", type=float)
    p.add_argument("--atol", type=float)
    p.add_argument("--note")
    p.add_argument("--agent")
    p.add_argument("--work-item")
    p.add_argument("--no-record", action="store_true", help="Do not keep the replay as a retest capsule")
    p.add_argument("--no-link", action="store_true", help="Do not record the retest on the DAG node")
    p = sub.add_parser("coverage", help="List the DAG's result nodes that have no capsule")
    p.add_argument("--verify", action="store_true", help="Also check every recorded capsule is intact")
    p.add_argument("--strict", action="store_true", help="Exit 1 when any result node has no capsule")
    p = sub.add_parser("lifecycle", help="Print GCS lifecycle rules that move old objects to colder classes")
    p.add_argument("--nearline", type=int, default=30)
    p.add_argument("--coldline", type=int, default=90)
    p.add_argument("--archive", type=int, default=365)

    args = ap.parse_args(argv)
    if getattr(args, "command", None) and args.command[:1] == ["--"]:
        args.command = args.command[1:]
    if getattr(args, "cmd", None):
        import shlex
        args.cmd_argv = shlex.split(args.cmd, posix=os.name != "nt")
    try:
        settings = Settings(args)
        if args.command_name == "init":
            return cmd_init(settings, args)
        if args.command_name == "run":
            return cmd_run(settings, args, observed=True)
        if args.command_name == "capture":
            return cmd_run(settings, args, observed=False)
        if args.command_name == "list":
            return cmd_list(settings, args)
        if args.command_name == "show":
            return cmd_show(settings, args)
        if args.command_name == "verify":
            return cmd_verify(settings, args)
        if args.command_name == "restore":
            settings.need()
            backend = open_backend(settings.uri)
            node, cid, m, _ = resolve(backend, settings, args.capsule, args.node)
            run_dir = restore(backend, m, Path(args.to).resolve())
            print(f"Restored {node}/{cid}; the run directory is {run_dir}. replay.sh or replay.ps1 runs it by hand.")
            return 0
        if args.command_name == "replay":
            return cmd_replay(settings, args)
        if args.command_name == "coverage":
            return cmd_coverage(settings, args)
        if args.command_name == "lifecycle":
            return cmd_lifecycle(settings, args)
    except VaultError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
