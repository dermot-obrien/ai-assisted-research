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
import stat
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
TOOL_VERSION = "1.4.0"

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
# gcloud settings that take priority over a credential file, or change who it acts as. A cloud
# session presets CLOUDSDK_AUTH_ACCESS_TOKEN as a placeholder for its proxy; left in place it, not
# the vault's key, would authenticate every call.
OVERRIDDEN_AUTH = ("CLOUDSDK_AUTH_ACCESS_TOKEN", "CLOUDSDK_AUTH_ACCESS_TOKEN_FILE",
                   "CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT", "CLOUDSDK_CORE_ACCOUNT")

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
    rest = argv[1:]
    if Path(argv[0]).name.lower() in ("git", "git.exe"):
        # No automatic gc or maintenance: git (2.56 on) may start it in the background after a fetch or
        # commit, still writing into .git/objects when the vault deletes a temporary repository.
        rest = ["-c", "gc.auto=0", "-c", "maintenance.auto=false", *rest]
    try:
        p = subprocess.run([exe, *rest], cwd=cwd, input=input_text, capture_output=True,
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
    env = {k: v for k, v in without_vault_keys(os.environ).items() if k not in OVERRIDDEN_AUTH}
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
                    "work_item_id", "work_item", "runtime")
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
    if manifest.get("evidence"):
        ref["evidence"] = manifest["evidence"]["class"]
    if manifest.get("runtime"):
        ref["runtime"] = {"name": manifest["runtime"]["name"], "match": manifest["runtime"]["match"]}
    machine = manifest.get("environment", {}).get("machine")
    if machine:
        ref["env"] = {k: machine.get(k) for k in ("tool", "os", "arch", "cpu", "python")}
    if manifest.get("upgrade"):
        ref["upgrade"] = True
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
                   environment: dict, run: dict, outputs: list[dict], metrics: dict | None,
                   datasets: list[dict] | None = None, evidence: dict | None = None,
                   runtime: dict | None = None) -> dict:
    manifest: dict[str, Any] = {
        "format": FORMAT, "tool": f"experiment-vault {TOOL_VERSION}", "kind": kind,
        "created_at": iso(now_utc()), "host": socket.gethostname(), "project": settings.project,
        "node": node_snapshot(settings, node), "code": code, "data": data, "environment": environment,
        "run": run, "outputs": outputs, "metrics": metrics,
        "tolerance": {"rtol": args.rtol if args.rtol is not None else settings.rtol,
                      "atol": args.atol if args.atol is not None else settings.atol},
    }
    if datasets:
        manifest["datasets"] = datasets
    if runtime:
        manifest["runtime"] = {k: v for k, v in runtime.items() if k != "tolerance"}
        manifest["tolerance"] = dict(runtime["tolerance"])
    if evidence:
        manifest["evidence"] = evidence
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
        snap = node_snapshot(settings, args.node).get("snapshot") if NAME_RE.match(args.node or "") else None
        if backend is not None and args.dataset:
            found = prepare_datasets(settings, backend, args.dataset, root, cwd, args.node, lineage(snap),
                                     args.override_holdout, dry=True, problems=problems)
            for d in found:
                w = d.get("window")
                notes.append(f"dataset {d['dataset']} {d['version']} at {d['mount']}"
                             + (f", window {w['window']} ({w['class']})" if w else ", no window"))
            notes.append(f"evidence class: {evidence_of(found, args.exploratory)['class']}")
        if backend is not None:
            cls = evidence_of(found if args.dataset else [], args.exploratory)["class"]
            try:
                rt = runtime_for_run(backend, snap, args, args.python or sys.executable, root, cls, observed)
                if rt:
                    notes.append(f"runtime {rt['name']}: " + ("matched" if rt["match"] else
                                 f"not matched ({len(rt['problems'])} difference(s)); exploratory only"))
            except VaultError as e:
                problems.append(str(e).replace("\n", " "))
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
        # Checked before any holdout is claimed, so a run refused for its runtime spends no look.
        runtime = runtime_for_run(backend, node_snapshot(settings, node).get("snapshot"), args,
                                  args.python or sys.executable, root,
                                  "exploratory" if args.exploratory else "evidence", observed)
        datasets = prepare_datasets(settings, backend, args.dataset or [], root, cwd, node,
                                    lineage(node_snapshot(settings, node).get("snapshot")), args.override_holdout,
                                    dry=False)
        evidence = evidence_of(datasets, args.exploratory)
        if runtime and runtime["match"] and runtime["tolerance"] != {"rtol": args.rtol, "atol": args.atol} \
                and (args.rtol is not None or args.atol is not None):
            print(f"note: runtime {runtime['name']} fixes the tolerance at rtol {runtime['tolerance']['rtol']}, "
                  f"atol {runtime['tolerance']['atol']}; --rtol and --atol are not used", file=sys.stderr)
        env_vars = recorded_env(args.env or [])
        if runtime:
            env_vars.update(runtime["env"])
        if "PYTHONHASHSEED" not in env_vars:
            print("note: PYTHONHASHSEED is not set, so set and dict-of-str iteration order can differ "
                  "between runs; set it for bit-identical replays", file=sys.stderr)
        seeds = dict(s.split("=", 1) for s in (args.seed or []))
        run: dict[str, Any] = {"argv": argv, "cwd": cwd.relative_to(root).as_posix() or ".",
                               "env": env_vars, "seeds": seeds, "observed": observed}
        started = now_utc()
        started_wall = time.time() - 0.001
        if observed:
            run_env = without_vault_keys(os.environ)
            if runtime:
                run_env.update(runtime["env"])
            if datasets:
                run_env["VAULT_DATASETS"] = str(datasets_env_file(datasets, root, work))
            code_rc, out_p, err_p, secs = tee_run(argv, cwd, run_env, work)
            run.update({"started_at": iso(started), "duration_s": secs, "exit_code": code_rc,
                        "stdout": blob_entry(out_p, blobs), "stderr": blob_entry(err_p, blobs)})
            for d in datasets:
                damage = cache_damage(root / d["mount"], load_version(backend, d["dataset"], d["version"])[0])
                if damage:
                    raise VaultError(f"the run changed dataset {d['dataset']} {d['version']} at {d['mount']} "
                                     f"({', '.join(damage[:5])}); datasets are read-only, so nothing was recorded. "
                                     f"Write outputs under --outputs")
        else:
            code_rc = args.exit_code
            run["exit_code"] = code_rc
            for k in ("stdout", "stderr"):
                if getattr(args, k):
                    run[k] = blob_entry(Path(getattr(args, k)).resolve(), blobs)
        environment = capture_environment(args.python or sys.executable,
                                          args.vendor_wheels or settings.vendor_wheels, work, blobs, args.strict)
        environment["machine"] = machine_summary(args.python or sys.executable, args)
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
                                  environment, run, outputs, metrics, datasets, evidence, runtime)
        if prior:
            tol = manifest["tolerance"]
            manifest["retest_of"] = f"{node}/{prior_id}"
            manifest["comparison"] = compare(prior, metrics, outputs, code_rc, tol["rtol"], tol["atol"])
        ref = write_capsule(backend, settings.project, node, manifest, blobs, files)
        record_uses(backend, settings.project, node, ref["id"], manifest)
    if datasets:
        print(f"  evidence: {evidence['class']}; data: "
              + ", ".join(f"{d['dataset']} {d['version']}" + (f" ({d['window']['window']})" if d.get('window') else "")
                          for d in datasets))
    if runtime:
        print(f"  runtime: {runtime['name']} ({'matched' if runtime['match'] else 'NOT matched: exploratory only'})")
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
    for d in manifest.get("datasets", []):
        record, digest = load_version(backend, d["dataset"], d["version"])
        if digest != d["sha256"]:
            raise VaultError(f"dataset {d['dataset']} {d['version']} in the vault is not the version the capsule "
                             f"used: it hashes to {digest[:12]}, the capsule recorded {d['sha256'][:12]}")
        link_folder(materialize(backend, d["dataset"], d["version"], record, digest), main / d["mount"])
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


def setup_uv(project: Path, record: dict | None) -> str:
    """The restored project's own uv environment, from its uv.lock, in the runtime's Python."""
    if not shutil.which("uv"):
        raise VaultError("--setup uv needs uv (https://docs.astral.sh/uv/); install it, or replay with --setup venv")
    if not (project / "uv.lock").is_file():
        raise VaultError(f"the restored project has no uv.lock; replay with --setup venv")
    cmd = ["uv", "sync", "--frozen"]
    if record:
        cmd += ["--python", record["python"]["version"]]
        if record["python"].get("managed"):
            cmd.append("--managed-python")
    print(f"Installing the locked environment: {' '.join(cmd)}")
    env = {k: v for k, v in without_vault_keys(os.environ).items() if k not in ("VIRTUAL_ENV", "UV_NATIVE_TLS")}
    p = subprocess.run(cmd, cwd=project, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        raise VaultError(f"uv sync failed: {(p.stdout + p.stderr).strip()[-400:]}")
    return str(project / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))


def cmd_replay(settings: Settings, args) -> int:
    settings.need()
    backend = open_backend(settings.uri)
    node, cid, manifest, _ = resolve(backend, settings, args.capsule, args.node)
    rt_name = args.runtime or (manifest.get("runtime") or {}).get("name")
    rt_record, rt_digest = load_runtime(backend, rt_name) if rt_name else (None, None)
    upgrade = None
    if args.upgrade:
        # A regression test: the capsule's own code, with the packages of a newer lock (and its runtime).
        source = Path(args.upgrade).resolve()
        if not (source / "uv.lock").is_file() or not (source / "pyproject.toml").is_file():
            raise VaultError(f"--upgrade {args.upgrade} must be a folder with pyproject.toml and uv.lock, such as "
                             f"a checkout where `uv lock --upgrade` was run")
        if args.setup not in (None, "uv"):
            raise VaultError("--upgrade installs the new uv.lock, so it needs --setup uv")
        args.setup = "uv"
        upgrade = {"lock_sha256": sha256_file(source / "uv.lock")[0],
                   "pyproject_sha256": sha256_file(source / "pyproject.toml")[0], "runtime": rt_name}
    if args.setup is None:
        args.setup = "uv" if rt_record else "venv"
    if args.pip and args.setup != "venv":
        raise VaultError("--pip needs --setup venv, so the overrides do not change your own environment")
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
    main_dir = dest / "repos" / manifest["code"][0]["name"]
    if args.setup == "venv":
        py = setup_venv(dest, manifest, base_python, args.pip or [])
    elif args.setup == "uv":
        if upgrade:
            for f in ("pyproject.toml", "uv.lock"):
                shutil.copyfile(Path(args.upgrade).resolve() / f, main_dir / f)
            print(f"Upgrading: the capsule's code with the packages of {args.upgrade}")
        py = setup_uv(main_dir, rt_record)
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
    if manifest.get("datasets"):
        main_dir = dest / "repos" / manifest["code"][0]["name"]
        env["VAULT_DATASETS"] = str(datasets_env_file(manifest["datasets"], main_dir, dest))
    if args.setup in ("venv", "uv"):
        env["VIRTUAL_ENV"] = str(Path(py).parent.parent)
        env["PATH"] = str(Path(py).parent) + os.pathsep + env.get("PATH", "")
    runtime = None
    if rt_record:
        problems = check_runtime(rt_record, py, main_dir)
        for line in problems:
            print(f"warning: runtime {rt_record['name']}: {line}", file=sys.stderr)
        runtime = {**(manifest.get("runtime") or {}), "name": rt_name, "sha256": rt_digest,
                   "profile": rt_record["profile"], "match": not problems, "problems": problems,
                   "tolerance": rt_record["tolerance"]}
        if rt_name != (manifest.get("runtime") or {}).get("name"):
            runtime["env"] = runtime_env(rt_record, py)
            env.update(runtime["env"])
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
            environment["machine"] = machine_summary(py, args)
            new_run = {**run, "argv": run["argv"], "observed": True, "started_at": iso(now_utc()),
                       "duration_s": secs, "exit_code": rc,
                       "stdout": blob_entry(out_p, blobs), "stderr": blob_entry(err_p, blobs),
                       "replay": {"setup": args.setup, "pip": args.pip or []}}
            if upgrade:
                new_run["replay"]["upgrade"] = upgrade
            if runtime:
                new_run["env"] = {**run.get("env", {}), **runtime["env"]}
            args.metric = (manifest.get("result") or {}).get("metric")
            args.target = (manifest.get("result") or {}).get("target")
            retest = build_manifest(settings, args, node, "retest", manifest["code"], manifest.get("data", []),
                                    environment, new_run, outputs, metrics, manifest.get("datasets"),
                                    manifest.get("evidence"), runtime)
            retest["tolerance"] = {"rtol": rtol, "atol": atol}
            retest["retest_of"] = f"{node}/{cid}"
            retest["comparison"] = comparison
            if upgrade:
                retest["upgrade"] = upgrade
            ref = write_capsule(backend, settings.project, node, retest, blobs)
            record_uses(backend, settings.project, node, ref["id"], retest)
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


# ---------------------------------------------------------------- runtimes

RUNTIME_FORMAT = "experiment-vault-runtime/1"
# numpy names the AVX-512 code paths by feature group from 2.4 on, and one by one before that; the first
# value the interpreter's own numpy accepts is used, and recorded, so a replay sets exactly the same.
NUMPY_AVX512_OFF = ("X86_V4 AVX512_ICL AVX512_SPR",
                    "AVX512F AVX512CD AVX512_KNL AVX512_KNM AVX512_SKX AVX512_CLX AVX512_CNL AVX512_ICL AVX512_SPR")
PROFILES: dict[str, dict] = {
    "cpu-deterministic-v1": {
        "description": "One thread for every numeric library, one fixed CPU code path (AVX2 and FMA, no AVX-512) "
                       "whatever the CPU, deterministic GPU kernels where a library offers them, and a fixed "
                       "hash seed, time zone and locale",
        "env": {"PYTHONHASHSEED": "0", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1", "BLIS_NUM_THREADS": "1",
                "OPENBLAS_CORETYPE": "Haswell", "MKL_CBWR": "AVX2,STRICT", "MKL_ENABLE_INSTRUCTIONS": "AVX2",
                "CUBLAS_WORKSPACE_CONFIG": ":4096:8", "TF_DETERMINISTIC_OPS": "1", "TF_CUDNN_DETERMINISTIC": "1",
                "TZ": "UTC", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"},
        "cpu_features": ["avx2", "fma"],
        "numpy_avx512": "off",
    },
    "none": {
        "description": "No settings: the runtime pins the machine type, the interpreter and the packages only",
        "env": {}, "cpu_features": [], "numpy_avx512": "as-is",
    },
}
CPU_FLAGS_KEPT = ("sse4_2", "avx", "avx2", "fma", "avx512f", "avx512bw", "avx512vl", "avx512dq", "avx512_vnni", "amx_tile")
MACHINE_PROBE = (
    "import json, platform, sys, sysconfig;"
    "print(json.dumps({'version': platform.python_version(), 'build': sys.version,"
    "'implementation': platform.python_implementation(), 'executable': sys.executable,"
    "'prefix': sys.prefix, 'base_prefix': sys.base_prefix, 'system': platform.system().lower(),"
    "'machine': platform.machine().lower(), 'libc': ' '.join(platform.libc_ver()).strip(),"
    "'kernel': platform.release()}))"
)


def cpu_flags() -> set[str]:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("flags"):
                    return set(line.split(":", 1)[1].split())
    except OSError:
        pass
    return set()


def os_release() -> str:
    try:
        fields = dict(l.rstrip("\n").split("=", 1) for l in open("/etc/os-release", encoding="utf-8") if "=" in l)
        return f"{fields.get('ID', '').strip(chr(34))} {fields.get('VERSION_ID', '').strip(chr(34))}".strip()
    except OSError:
        return f"{platform.system()} {platform.release()}"


def agent_tool(args) -> str:
    """Which agent platform made the run: --tool, else VAULT_AGENT_TOOL, else what the environment shows."""
    named = getattr(args, "tool", None) or os.environ.get("VAULT_AGENT_TOOL")
    if named:
        return named
    if os.environ.get("CLAUDECODE"):
        return "claude-code-remote" if os.environ.get("CLAUDE_CODE_REMOTE") else "claude-code"
    return "unknown"


def probe_machine(python: str) -> dict:
    p = run_cmd([python, "-c", MACHINE_PROBE], check=False)
    if p.returncode != 0:
        raise VaultError(f"cannot run {python}: {p.stderr.strip()[:200]}")
    return json.loads(p.stdout)


def machine_summary(python: str, args) -> dict:
    """Where a run ran, as a capsule's environment and the DAG's capsule entry record it."""
    try:
        m = probe_machine(python)
    except VaultError:
        m = {"system": platform.system().lower(), "machine": platform.machine().lower(), "version": "?"}
    flags = cpu_flags()
    return {"tool": agent_tool(args), "os": os_release(), "arch": f"{m['system']}-{m['machine']}",
            "kernel": m.get("kernel", platform.release()), "libc": m.get("libc", ""),
            "cpu": hardware().get("cpu", ""), "cpu_flags": sorted(f for f in CPU_FLAGS_KEPT if f in flags),
            "python": m.get("version"), "python_build": m.get("build")}


def rt_key(name: str) -> str:
    return f"runtimes/{name}.json"


def load_runtime(backend: Backend, name: str) -> tuple[dict, str]:
    if not NAME_RE.match(name or ""):
        raise VaultError(f"runtime name {name!r} must be letters, digits, '.', '_' or '-'")
    got = read_json(backend, rt_key(name))
    if got is None:
        raise VaultError(f"there is no runtime {name}; define it with vault.py runtime create {name} --python <interpreter>")
    record, digest = got
    if record.get("format") != RUNTIME_FORMAT:
        raise VaultError(f"runtime {name} has format {record.get('format')}; update the skill to read it")
    return record, digest


def numpy_setting(python: str) -> str | None:
    """The value of NPY_DISABLE_CPU_FEATURES that turns AVX-512 off for this interpreter's numpy, or None
    when numpy is not installed."""
    if run_cmd([python, "-c", "import numpy"], check=False).returncode != 0:
        return None
    for value in NUMPY_AVX512_OFF:
        env = {**os.environ, "NPY_DISABLE_CPU_FEATURES": value}
        p = subprocess.run([python, "-c", "import numpy"], env=env, capture_output=True, text=True)
        if p.returncode == 0 and not p.stderr.strip():
            return value
    raise VaultError(f"the numpy of {python} accepts none of the known ways to turn AVX-512 off; "
                     f"update the skill for this numpy")


def runtime_env(record: dict, python: str) -> dict[str, str]:
    profile = PROFILES[record["profile"]]
    env = dict(profile["env"])
    if profile.get("numpy_avx512") == "off":
        value = numpy_setting(python)
        if value:
            env["NPY_DISABLE_CPU_FEATURES"] = value
    return env


def check_runtime(record: dict, python: str, root: Path | None) -> list[str]:
    """Every way this machine, interpreter and environment differ from the runtime; empty when they match."""
    problems = []
    try:
        m = probe_machine(python)
    except VaultError as e:
        return [str(e)]
    arch = f"{m['system']}-{m['machine']}"
    if arch != record["arch"]:
        problems.append(f"this machine is {arch}; runtime {record['name']} is {record['arch']}")
    want = record["python"]
    if m["version"] != want["version"] or m["build"] != want["build"]:
        problems.append(f"the interpreter is Python {m['version']} ({m['build'].splitlines()[0]}); runtime "
                        f"{record['name']} is {want['version']} ({want['build'].splitlines()[0]})"
                        + (". Install it with: uv python install " + want["version"] if want.get("managed") else ""))
    missing = [f for f in PROFILES[record["profile"]]["cpu_features"] if f not in cpu_flags()]
    if missing:
        problems.append(f"this CPU lacks {', '.join(missing)}, which profile {record['profile']} needs")
    if record.get("lock") == "uv" and root is not None:
        if not shutil.which("uv"):
            problems.append("uv is not installed, so the environment cannot be checked against uv.lock")
        elif not (root / "uv.lock").is_file():
            problems.append(f"{root} has no uv.lock; runtime {record['name']} runs only from a locked uv project")
        elif m["prefix"] == m["base_prefix"]:
            problems.append(f"{python} is not the project's environment; run `uv sync --frozen` and use "
                            f"{root / '.venv' / 'bin' / 'python'}")
        else:
            env = {**without_vault_keys(os.environ), "VIRTUAL_ENV": m["prefix"]}
            env.pop("UV_NATIVE_TLS", None)
            p = subprocess.run(["uv", "sync", "--frozen", "--check", "--active"], cwd=root, env=env,
                               capture_output=True, text=True)
            if p.returncode != 0:
                lines = [l for l in (p.stdout + p.stderr).splitlines() if l.strip() and "warning:" not in l]
                problems.append("the environment does not match uv.lock: " + "; ".join(lines[-4:])
                                + ". Run `uv sync --frozen`")
    return problems


def runtime_for_run(backend: Backend, snap: dict | None, args, python: str, root: Path,
                    evidence_class: str, observed: bool) -> dict | None:
    """The runtime the node fixes (or --runtime names), checked against this machine. Refuses an evidence
    run that does not match; an exploratory run is recorded with what differed."""
    named = getattr(args, "runtime", None)
    fixed = (snap or {}).get("runtime")
    if named and fixed and named != fixed:
        raise VaultError(f"the node fixes runtime {fixed}; --runtime {named} names another")
    name = named or fixed
    if not name:
        return None
    record, digest = load_runtime(backend, name)
    problems = check_runtime(record, python, root)
    if not observed:
        problems.append("a capture cannot show the machine a past run ran on")
    evidence = evidence_class != "exploratory"
    if problems and evidence:
        raise VaultError(f"this run does not match runtime {name}, so it cannot be evidence:\n  - "
                         + "\n  - ".join(problems)
                         + "\nFix them, or run with --exploratory (kept, never evidence)")
    for line in problems:
        print(f"warning: runtime {name}: {line}", file=sys.stderr)
    env = runtime_env(record, python) if not any("cannot run" in p for p in problems) else {}
    return {"name": name, "sha256": digest, "profile": record["profile"], "env": env, "match": not problems,
            "problems": problems, "tolerance": record["tolerance"]}


def cmd_runtime_create(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    if not NAME_RE.match(args.name):
        raise VaultError(f"runtime name {args.name!r} must be letters, digits, '.', '_' or '-'")
    if args.profile not in PROFILES:
        raise VaultError(f"unknown profile {args.profile}; the profiles are {', '.join(PROFILES)}")
    m = probe_machine(args.python)
    managed = False
    if shutil.which("uv"):
        p = run_cmd(["uv", "python", "dir"], check=False)
        managed = p.returncode == 0 and Path(m["executable"]).resolve().is_relative_to(Path(p.stdout.strip()).resolve())
    record = {"format": RUNTIME_FORMAT, "name": args.name, "arch": f"{m['system']}-{m['machine']}",
              "python": {"version": m["version"], "build": m["build"], "implementation": m["implementation"],
                         "managed": managed},
              "lock": "uv", "profile": args.profile, "tolerance": {"rtol": args.rtol, "atol": args.atol},
              "parity": not args.no_parity, "created_at": iso(now_utc()), "host": socket.gethostname()}
    if args.note:
        record["note"] = args.note
    if not managed:
        print(f"warning: {m['executable']} is not a uv-managed Python, so other machines may not find the same "
              f"build; `uv python install {m['version']}` gives the same build everywhere", file=sys.stderr)
    if not backend.write_once(rt_key(args.name), canonical(record)):
        raise VaultError(f"runtime {args.name} already exists; a runtime is defined once. Name a new one")
    print(f"Defined runtime {args.name}: {record['arch']}, Python {m['version']}"
          f"{' (uv-managed)' if managed else ''}, uv.lock, profile {args.profile}, "
          f"rtol {args.rtol}, atol {args.atol}, {'parity required' if record['parity'] else 'no parity check'}")
    return 0


def cmd_runtime_show(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    if args.name:
        record, digest = load_runtime(backend, args.name)
        print(json.dumps({**record, "sha256": digest, "profile_env": PROFILES[record["profile"]]["env"]}, indent=2))
        return 0
    names = sorted(k[len("runtimes/"):-len(".json")] for k in backend.list("runtimes/") if k.endswith(".json"))
    if not names:
        print("No runtimes yet.")
    for n in names:
        r, _ = load_runtime(backend, n)
        print(f"{n}  {r['arch']}  Python {r['python']['version']}  {r['profile']}  rtol {r['tolerance']['rtol']}")
    return 0


def cmd_runtime_check(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    record, _ = load_runtime(backend, args.name)
    python = args.python or sys.executable
    try:
        root = Path(git(["rev-parse", "--show-toplevel"], Path(args.cwd).resolve())).resolve()
    except VaultError:
        root = Path(args.cwd).resolve()
    problems = check_runtime(record, python, root)
    m = machine_summary(python, args)
    print(f"This machine: {m['tool']}, {m['os']}, {m['arch']}, {m['cpu']}, Python {m['python']}")
    for line in problems:
        print(f"PROBLEM {line}")
    print(f"matches runtime {args.name}" if not problems else f"does not match runtime {args.name}: {len(problems)} problem(s)")
    return 0 if not problems else 2


def cmd_parity(settings: Settings, args) -> int:
    """Whether a capsule was replayed identically on another machine in its runtime: the check a result on a
    node with a runtime needs before its status moves."""
    settings.need()
    backend = open_backend(settings.uri)
    node, cid, manifest, _ = resolve(backend, settings, args.capsule, args.node)
    where = manifest.get("environment", {}).get("machine", {})
    prefix = f"capsules/{settings.project}/{node}/"
    found = []
    for key in backend.list(prefix):
        if not key.endswith(".json") or key.endswith(f"/{cid}.json"):
            continue
        got = read_json(backend, key)
        if not got:
            continue
        m = got[0]
        if m.get("retest_of") != f"{node}/{cid}":
            continue
        other = m.get("environment", {}).get("machine", {})
        elsewhere = m.get("host") != manifest.get("host") or other.get("tool") != where.get("tool")
        same_runtime = (m.get("runtime") or {}).get("name") == (manifest.get("runtime") or {}).get("name")
        ok = ((m.get("comparison") or {}).get("verdict") == "identical" and (m.get("runtime") or {}).get("match")
              and same_runtime and not m.get("upgrade") and elsewhere)
        found.append((ok, key.rsplit("/", 1)[1][:-5], m, other))
    for ok, rid, m, other in found:
        print(f"{'ok  ' if ok else '    '}{rid}  {(m.get('comparison') or {}).get('verdict')}  "
              f"{other.get('tool', '?')} on {m.get('host')}  runtime {'matched' if (m.get('runtime') or {}).get('match') else 'not matched'}")
    passed = any(ok for ok, *_ in found)
    print(f"parity: {node}/{cid} " + ("was replayed identically on another machine in its runtime" if passed
                                      else "has no identical replay on another machine in its runtime yet"))
    return 0 if passed else 1


# ---------------------------------------------------------------- datasets

DATASET_FORMAT = "experiment-vault-dataset/1"
DATASET_RULES = ("append-only", "revisable", "frozen")
WINDOW_CLASSES = ("backtest", "holdout", "forward")
VERSION_RE = re.compile(r"^v(\d{4,})$")


def ds_key(name: str, *parts: str) -> str:
    return "/".join(["datasets", name, *parts])


def read_json(backend: Backend, key: str) -> tuple[dict, str] | None:
    """(record, sha256 of its bytes) for a JSON object in the vault, or None when it is not there."""
    data = backend.read(key)
    if data is None:
        return None
    return json.loads(data), hashlib.sha256(data).hexdigest()


def check_dataset_name(name: str) -> str:
    if not NAME_RE.match(name):
        raise VaultError(f"dataset name {name!r} must be letters, digits, '.', '_' or '-'")
    return name


def dataset_descriptor(backend: Backend, name: str) -> dict:
    got = read_json(backend, ds_key(check_dataset_name(name), "dataset.json"))
    if got is None:
        raise VaultError(f"there is no dataset {name}; create it with vault.py dataset create")
    return got[0]


def dataset_versions(backend: Backend, name: str) -> list[str]:
    prefix = ds_key(name, "versions") + "/"
    found = []
    for key in backend.list(prefix):
        stem = key[len(prefix):-len(".json")] if key.endswith(".json") else ""
        if VERSION_RE.match(stem):
            found.append(stem)
    return sorted(found, key=lambda v: int(v[1:]))


def resolve_version(backend: Backend, name: str, ref: str) -> str:
    versions = dataset_versions(backend, name)
    if not versions:
        raise VaultError(f"dataset {name} has no versions yet; add one with vault.py dataset add")
    if ref in ("", "latest"):
        return versions[-1]
    if ref not in versions:
        raise VaultError(f"dataset {name} has no version {ref}; it has {', '.join(versions[-5:])}")
    return ref


def load_version(backend: Backend, name: str, version: str) -> tuple[dict, str]:
    got = read_json(backend, ds_key(name, "versions", f"{version}.json"))
    if got is None:
        raise VaultError(f"dataset {name} has no version {version}")
    return got


def load_window(backend: Backend, name: str, window: str) -> dict:
    if not NAME_RE.match(window):
        raise VaultError(f"window name {window!r} must be letters, digits, '.', '_' or '-'")
    got = read_json(backend, ds_key(name, "windows", f"{window}.json"))
    if got is None:
        raise VaultError(f"dataset {name} has no window {window}; define it with vault.py dataset window")
    return got[0]


def dataset_windows(backend: Backend, name: str) -> list[dict]:
    prefix = ds_key(name, "windows") + "/"
    keys = [k for k in backend.list(prefix) if k.endswith(".json") and "/" not in k[len(prefix):]]
    return [read_json(backend, k)[0] for k in sorted(keys)]


def overlaps(a: dict, b: dict) -> bool:
    """Whether two date windows share any time; a missing end is open. Dates compare as ISO text."""
    lo = max(a.get("from_date") or "", b.get("from_date") or "")
    hi = min(a.get("to_date") or "\uffff", b.get("to_date") or "\uffff")
    return lo <= hi


def scan_folder(folder: Path) -> dict[str, tuple[str, int, Path]]:
    """{posix path relative to folder: (sha256, size, file)} for every file under folder, links followed."""
    if not folder.is_dir():
        raise VaultError(f"{folder} is not a folder")
    out = {}
    for dp, _, fns in os.walk(folder, followlinks=True):
        for fn in fns:
            f = Path(dp) / fn
            if f.is_file():
                hexd, size = sha256_file(f)
                out[f.relative_to(folder).as_posix()] = (hexd, size, f)
    if not out:
        raise VaultError(f"{folder} holds no files")
    return dict(sorted(out.items()))


def prefix_sha256(path: Path, n: int) -> str:
    h = hashlib.sha256()
    left = n
    with open(path, "rb") as f:
        while left > 0:
            chunk = f.read(min(1 << 20, left))
            if not chunk:
                break
            h.update(chunk)
            left -= len(chunk)
    return h.hexdigest()


def classify_changes(parent: dict[str, dict], scan: dict[str, tuple[str, int, Path]]) -> dict[str, list]:
    """How a folder differs from a version: files added, extended at the end, changed, removed."""
    changes: dict[str, list] = {"added": [], "extended": [], "changed": [], "removed": []}
    for path, old in parent.items():
        if path not in scan:
            changes["removed"].append(path)
            continue
        hexd, size, f = scan[path]
        if hexd == old["sha256"]:
            continue
        if size > old["size"] and prefix_sha256(f, old["size"]) == old["sha256"]:
            changes["extended"].append({"path": path, "from_size": old["size"], "to_size": size})
        else:
            changes["changed"].append(path)
    changes["added"] = [p for p in scan if p not in parent]
    return changes


def confirm_person(what: str, name: str) -> None:
    """Stop unless a person at a terminal confirms by typing the dataset's name. Agents run without one."""
    if not sys.stdin.isatty() or os.environ.get("CI"):
        raise VaultError(f"{what} needs a person: run it yourself at a terminal, not through an agent or a script")
    typed = input(f"{what}. Type the dataset's name ({name}) to confirm: ").strip()
    if typed != name:
        raise VaultError("not confirmed; nothing was written")


def cmd_dataset_create(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    name = check_dataset_name(args.name)
    record = {"format": DATASET_FORMAT, "name": name, "rule": args.rule, "title": args.title or name,
              "description": args.description or "", "sources": args.source or [], "licence": args.licence or "",
              "owner": args.owner or "", "created_at": iso(now_utc()), "host": socket.gethostname()}
    if args.agent:
        record["agent"] = args.agent
    if not backend.write_once(ds_key(name, "dataset.json"), canonical(record)):
        raise VaultError(f"dataset {name} already exists; a dataset's description is written once")
    print(f"Created dataset {name} ({args.rule}). Add its first version with: vault.py dataset add {name} --from <folder>")
    return 0


def cmd_dataset_add(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    name = check_dataset_name(args.name)
    desc = dataset_descriptor(backend, name)
    versions = dataset_versions(backend, name)
    parent_v = versions[-1] if versions else None
    parent_files = load_version(backend, name, parent_v)[0]["files"] if parent_v else {}
    scan = scan_folder(Path(args.source_folder).resolve())
    changes = classify_changes(parent_files, scan)
    if not any(changes.values()):
        print(f"No change from {name} {parent_v}; no version added.")
        return 0
    rewrites = changes["changed"] + changes["removed"]
    if parent_v and desc["rule"] == "frozen":
        raise VaultError(f"dataset {name} is frozen: it has one version, {parent_v}, and takes no other. "
                         f"Register the new data as a dataset of its own.")
    if rewrites and not args.revise:
        raise VaultError(f"dataset {name} is {desc['rule']}, and this folder changes or removes "
                         f"{len(rewrites)} file(s) of {parent_v}: {', '.join(rewrites[:5])}. Only adding files and "
                         f"extending files at their end is allowed; a change is a revision (--revise \"<reason>\"), "
                         f"which a person makes")
    if args.revise:
        if not rewrites:
            raise VaultError("--revise is for changing or removing data; this folder only adds to it")
        if desc["rule"] == "append-only" and not args.allow_append_only_revision:
            raise VaultError(f"dataset {name} is append-only: it is never revised. If its history really is wrong, "
                             f"pass --allow-append-only-revision too, and every result built on it will be listed "
                             f"for retesting")
        if desc["rule"] == "append-only":
            confirm_person(f"Revising append-only {name}: {len(rewrites)} file(s) of {parent_v} change", name)
    blobs = {sha: f for sha, _, f in scan.values()}
    with tempfile.TemporaryDirectory(prefix="vault-") as td:
        extra = {}
        if args.source_checksums:
            extra["source_checksums"] = blob_entry(Path(args.source_checksums).resolve(), blobs)
        sent = backend.put_blobs(blobs)
        number = int(parent_v[1:]) + 1 if parent_v else 1
        version = f"v{number:04d}"
        record = {"format": DATASET_FORMAT, "dataset": name, "version": version, "parent": parent_v,
                  "created_at": iso(now_utc()), "host": socket.gethostname(),
                  "files": {p: {"sha256": h, "size": n} for p, (h, n, _) in scan.items()},
                  "changes": changes, "revision": args.revise or None,
                  "totals": {"files": len(scan), "bytes": sum(n for _, n, _ in scan.values())}, **extra}
        for k in ("note", "source", "fetched_by", "agent"):
            if getattr(args, k, None):
                record[k] = getattr(args, k)
        if not backend.write_once(ds_key(name, "versions", f"{version}.json"), canonical(record)):
            raise VaultError(f"another version {version} of {name} was added at the same moment; run again")
    print(f"Added {name} {version}: {len(changes['added'])} added, {len(changes['extended'])} extended, "
          f"{len(changes['changed'])} changed, {len(changes['removed'])} removed; {sent} new file(s) to the vault")
    if args.revise:
        print("This is a revision. Results built on earlier versions:")
        print_impact(backend, name, version)
    return 0


def cmd_dataset_window(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    name = check_dataset_name(args.name)
    desc = dataset_descriptor(backend, name)
    if not NAME_RE.match(args.window):
        raise VaultError(f"window name {args.window!r} must be letters, digits, '.', '_' or '-'")
    record: dict[str, Any] = {"format": DATASET_FORMAT, "dataset": name, "window": args.window, "class": args.cls,
                              "created_at": iso(now_utc()), "host": socket.gethostname()}
    if args.cls == "forward":
        if desc["rule"] != "append-only":
            raise VaultError("a forward window needs an append-only dataset, so the data after it is exactly the "
                             "data added since")
        if not args.from_version:
            raise VaultError("a forward window starts at a version: pass --from-version <version>")
        record["from_version"] = resolve_version(backend, name, args.from_version)
    else:
        if not (args.from_date or args.to_date):
            raise VaultError(f"a {args.cls} window is a span of time: pass --from-date and --to-date")
        record["from_date"], record["to_date"] = args.from_date, args.to_date
        for other in dataset_windows(backend, name):
            pair = {other["class"], args.cls}
            if pair == {"backtest", "holdout"} and overlaps(other, record):
                raise VaultError(f"{args.window} ({args.cls}) overlaps {other['class']} window {other['window']} "
                                 f"({other.get('from_date') or '...'} to {other.get('to_date') or '...'}): a holdout "
                                 f"is data no backtest has seen")
    if args.note:
        record["note"] = args.note
    if not backend.write_once(ds_key(name, "windows", f"{args.window}.json"), canonical(record)):
        raise VaultError(f"dataset {name} already has a window {args.window}; a window is defined once")
    sealed = " It is sealed: each node may look once, and no sibling of a node that looked may." if args.cls == "holdout" else ""
    print(f"Defined {args.cls} window {args.window} on {name}.{sealed}")
    return 0


def dataset_uses(backend: Backend, name: str) -> list[dict]:
    prefix = ds_key(name, "used-by") + "/"
    out = []
    for key in backend.list(prefix):
        if key.endswith(".json"):
            got = read_json(backend, key)
            if got:
                out.append(got[0])
    return sorted(out, key=lambda u: u.get("at", ""))


def print_impact(backend: Backend, name: str, version: str) -> list[dict]:
    n = int(version[1:])
    older = [u for u in dataset_uses(backend, name) if int(u["version"][1:]) < n]
    if not older:
        print("  none")
    for u in older:
        print(f"  {u['project']}/{u['node']}/{u['capsule']}  on {u['version']}  {u.get('class', '')}")
    return older


def cmd_dataset_list(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    names = sorted({k.split("/")[1] for k in backend.list("datasets/") if k.endswith("/dataset.json")})
    if not names:
        print("No datasets yet.")
    for name in names:
        desc = dataset_descriptor(backend, name)
        versions = dataset_versions(backend, name)
        print(f"{name}  {desc['rule']}  {len(versions)} version(s), latest {versions[-1] if versions else '-'}  "
              f"{desc.get('title', '')}")
    return 0


def cmd_dataset_show(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    name, _, ref = args.ref.partition("@")
    desc = dataset_descriptor(backend, name)
    if not ref:
        print(json.dumps(desc, indent=2, ensure_ascii=False))
        for v in dataset_versions(backend, name):
            rec, _ = load_version(backend, name, v)
            ch = rec["changes"]
            print(f"  {v}  {rec['created_at']}  {rec['totals']['files']} files, {human(rec['totals']['bytes'])}  "
                  f"+{len(ch['added'])} >{len(ch['extended'])} ~{len(ch['changed'])} -{len(ch['removed'])}"
                  f"{'  REVISION: ' + rec['revision'] if rec.get('revision') else ''}")
        windows = [k for k in backend.list(ds_key(name, "windows") + "/") if k.count("/") == 3 and k.endswith(".json")]
        for k in windows:
            w = read_json(backend, k)[0]
            span = f"from {w['from_version']}" if "from_version" in w else f"{w.get('from_date')} to {w.get('to_date')}"
            print(f"  window {w['window']}  {w['class']}  {span}")
        return 0
    version = resolve_version(backend, name, ref)
    rec, digest = load_version(backend, name, version)
    rec = {**rec, "sha256": digest}
    if not args.files:
        rec["files"] = f"{len(rec['files'])} files (--files to list them)"
    print(json.dumps(rec, indent=2, ensure_ascii=False))
    return 0


def cmd_dataset_diff(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    (a_name, _, a_ref), (b_name, _, b_ref) = args.a.partition("@"), args.b.partition("@")
    if a_name != b_name:
        raise VaultError("diff compares two versions of one dataset")
    a = load_version(backend, a_name, resolve_version(backend, a_name, a_ref))[0]["files"]
    b = load_version(backend, b_name, resolve_version(backend, b_name, b_ref))[0]["files"]
    for path in sorted(set(a) | set(b)):
        if path not in b:
            print(f"- {path}")
        elif path not in a:
            print(f"+ {path}  {human(b[path]['size'])}")
        elif a[path]["sha256"] != b[path]["sha256"]:
            print(f"~ {path}  {human(a[path]['size'])} -> {human(b[path]['size'])}")
    return 0


def cache_root() -> Path:
    env = os.environ.get("RESEARCH_VAULT_CACHE")
    return Path(env).expanduser() if env else Path.home() / ".cache" / "experiment-vault"


def materialize(backend: Backend, name: str, version: str, record: dict, digest: str) -> Path:
    """The version's files in the local cache, read-only, hash-checked once and reused after."""
    target = cache_root() / "datasets" / name / version
    marker = target / ".vault-verified"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == digest and not cache_damage(target, record):
        return target
    if target.exists():
        def writable(func, p, _):
            os.chmod(p, stat.S_IWRITE)
            func(p)
        if sys.version_info >= (3, 12):
            shutil.rmtree(target, onexc=writable)
        else:
            shutil.rmtree(target, onerror=writable)
    with tempfile.TemporaryDirectory(prefix="vault-") as td:
        cache = Path(td)
        hexes = {e["sha256"] for e in record["files"].values()}
        backend.get_blobs(hexes, cache)
        for hexd in hexes:
            if sha256_file(cache / hexd)[0] != hexd:
                raise VaultError(f"blob {hexd} of {name} {version} is corrupt in {backend.uri}")
        for path, e in record["files"].items():
            place(cache / e["sha256"], target / path)
            os.chmod(target / path, 0o444)
    marker.write_text(digest + "\n", encoding="utf-8")
    return target


def cache_damage(target: Path, record: dict) -> list[str]:
    """Files of a cached version that are missing, added or of the wrong size: a cheap check made on every use
    (a full re-hash is verify --deep's job), so an experiment that wrote into its data is caught."""
    found = {}
    for dp, _, fns in os.walk(target):
        for fn in fns:
            f = Path(dp) / fn
            rel = f.relative_to(target).as_posix()
            if rel != ".vault-verified":
                found[rel] = f.stat().st_size
    want = {p: e["size"] for p, e in record["files"].items()}
    return sorted(p for p in set(found) | set(want) if found.get(p) != want.get(p))


def link_folder(target: Path, mount: Path) -> None:
    """Make mount point at target: a symlink, else (Windows) a junction, else a read-only copy."""
    mount.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(target, mount, target_is_directory=True)
        return
    except (OSError, NotImplementedError):
        pass
    if os.name == "nt":
        p = subprocess.run(["cmd", "/c", "mklink", "/J", str(mount), str(target)], capture_output=True, text=True)
        if p.returncode == 0:
            return
    shutil.copytree(target, mount)


def same_folder(a: Path, b: Path) -> bool:
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def parse_dataset_arg(text: str) -> tuple[str, str, str, str | None]:
    """name@version:mount[:window] -> (name, version, mount, window)."""
    head, sep, rest = text.partition(":")
    if not sep or not rest:
        raise VaultError(f"--dataset {text!r}: write it as name@version:mount[:window], e.g. stocks-eod@latest:data/eod")
    name, _, version = head.partition("@")
    mount, _, window = rest.partition(":")
    return check_dataset_name(name), version or "latest", mount, window or None


def lineage(snapshot: dict | None) -> dict | None:
    """The node's place in the DAG, which a holdout claim needs to find its siblings; None if not in the DAG."""
    if snapshot is None:
        return None
    parent = snapshot.get("parent")
    return {"parent": parent if isinstance(parent, str) and parent else None}


def prepare_datasets(settings: Settings, backend: Backend, specs: list[str], root: Path, cwd: Path,
                     node: str, place: dict | None, override: str | None, dry: bool,
                     problems: list[str] | None = None) -> list[dict]:
    """Resolve, fetch and mount each --dataset, check its window, and claim sealed holdouts."""
    out = []
    for spec in specs:
        try:
            name, ref, mount_rel, window_name = parse_dataset_arg(spec)
            dataset_descriptor(backend, name)
            version = resolve_version(backend, name, ref)
            record, digest = load_version(backend, name, version)
            mount = Path(os.path.abspath(cwd / mount_rel))
            if not mount.is_relative_to(root):
                raise VaultError(f"dataset mount {mount_rel} is outside {root}")
            ignored = run_cmd(["git", "check-ignore", "-q", str(mount)], cwd=root, check=False).returncode == 0
            if not ignored:
                raise VaultError(f"{mount.relative_to(root).as_posix()} is not git-ignored, so mounting {name} there "
                                 f"would make the repository dirty. Add it to .gitignore")
            entry: dict[str, Any] = {"dataset": name, "version": version, "sha256": digest,
                                     "mount": mount.relative_to(root).as_posix()}
            if not window_name and any(w["class"] == "holdout" for w in dataset_windows(backend, name)):
                raise VaultError(f"dataset {name} has a sealed holdout, so a run on it names its window "
                                 f"({name}@{ref or 'latest'}:{mount_rel}:<window>), and reads only that window")
            if window_name:
                w = load_window(backend, name, window_name)
                entry["window"] = {k: w[k] for k in ("window", "class", "from_date", "to_date", "from_version") if k in w}
                if w["class"] == "forward":
                    start_files = load_version(backend, name, w["from_version"])[0]["files"]
                    if int(version[1:]) <= int(w["from_version"][1:]):
                        raise VaultError(f"forward window {window_name} starts after {w['from_version']}; "
                                         f"{version} holds no forward data yet")
                    entry["forward_offsets"] = {p: start_files[p]["size"] if p in start_files else 0
                                                for p in record["files"]}
                if w["class"] == "holdout":
                    if place is None:
                        raise VaultError(f"{node} is not in the DAG, so its siblings cannot be checked against "
                                         f"holdout {window_name} of {name}; add the node (and refresh the view) first")
                    claim_holdout(backend, name, window_name, node, place["parent"], override, dry)
            if not dry:
                target = materialize(backend, name, version, record, digest)
                if mount.exists() or mount.is_symlink():
                    if not same_folder(mount, target):
                        raise VaultError(f"{entry['mount']} already exists and is not {name} {version}; remove it "
                                         f"(it is git-ignored) and run again")
                else:
                    link_folder(target, mount)
            out.append(entry)
        except VaultError as e:
            if problems is None:
                raise
            problems.append(str(e))
    classes = {d["window"]["class"] for d in out if d.get("window")}
    if len(classes) > 1:
        msg = f"one test has one evidence class; these windows mix {', '.join(sorted(classes))}"
        if problems is None:
            raise VaultError(msg)
        problems.append(msg)
    return out


def claim_holdout(backend: Backend, name: str, window: str, node: str, parent: str | None,
                  override: str | None, dry: bool) -> None:
    """A sealed holdout gives each node one look, and none to a sibling of a node that looked."""
    prefix = ds_key(name, "windows", window, "claims") + "/"
    claims = [read_json(backend, k)[0] for k in backend.list(prefix) if k.endswith(".json")]
    clash = [c for c in claims if c["node"] == node or (parent and c.get("parent") == parent)]
    if clash and not override:
        who = ", ".join(sorted({c["node"] for c in clash}))
        raise VaultError(f"holdout {window} of {name} was already looked at by {who} "
                         f"({'this node' if any(c['node'] == node for c in clash) else 'a sibling of this node'}). "
                         f"A sealed holdout gives one look; a person may override with --override-holdout \"<reason>\"")
    if dry:
        if clash or override:
            print(f"  note: overriding holdout {window} of {name} needs a person at a terminal", file=sys.stderr)
        return
    claim = {"node": node, "parent": parent, "at": iso(now_utc()), "host": socket.gethostname()}
    key = prefix + f"{node}.json"
    if clash or override:
        confirm_person(f"Overriding holdout {window} of {name} for {node}: {override}", name)
        claim["override"] = override
        key = prefix + f"{node}-override-{now_utc().strftime('%Y%m%dT%H%M%SZ')}.json"
    if not backend.write_once(key, canonical(claim)):
        raise VaultError(f"holdout {window} of {name} was claimed for {node} at the same moment; it has had its look")


def record_uses(backend: Backend, project: str, node: str, cid: str, manifest: dict) -> None:
    for d in manifest.get("datasets", []):
        use = {"project": project, "node": node, "capsule": cid, "version": d["version"],
               "class": (d.get("window") or {}).get("class", "untracked"), "at": manifest["created_at"]}
        if d.get("window"):
            use["window"] = d["window"]["window"]
        backend.write_once(ds_key(d["dataset"], "used-by", f"{project}--{node}--{cid}.json"), canonical(use))


def evidence_of(datasets: list[dict], exploratory: bool) -> dict:
    windows = [{"dataset": d["dataset"], "window": d["window"]["window"], "class": d["window"]["class"]}
               for d in datasets if d.get("window")]
    if exploratory:
        cls = "exploratory"
    elif windows:
        cls = windows[0]["class"]
    else:
        cls = "untracked"
    return {"class": cls, "windows": windows}


def datasets_env_file(datasets: list[dict], root: Path, work: Path) -> Path:
    """The file VAULT_DATASETS names: each dataset's version, folder, window and, for a forward window,
    the byte in each file where the forward data starts."""
    body = {d["dataset"]: {"version": d["version"], "path": str(root / d["mount"]), "window": d.get("window"),
                           "forward_offsets": d.get("forward_offsets")} for d in datasets}
    path = work / "vault-datasets.json"
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return path


def cmd_dataset_fetch(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    name, _, ref = args.ref.partition("@")
    version = resolve_version(backend, check_dataset_name(name), ref)
    record, digest = load_version(backend, name, version)
    target = materialize(backend, name, version, record, digest)
    if args.to:
        dest = Path(args.to).resolve()
        if dest.exists() and any(dest.iterdir()):
            raise VaultError(f"{dest} is not empty")
        shutil.copytree(target, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".vault-verified"))
        print(f"Fetched {name} {version} into {dest}")
    else:
        print(f"Fetched {name} {version} into the cache: {target}")
    return 0


def cmd_dataset_uses(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    name = check_dataset_name(args.name)
    for u in dataset_uses(backend, name):
        print(f"{u['project']}/{u['node']}/{u['capsule']}  {u['version']}  {u['class']}  {u.get('window', '')}")
    if args.window:
        prefix = ds_key(name, "windows", args.window, "claims") + "/"
        for k in backend.list(prefix):
            c = read_json(backend, k)[0]
            print(f"claim  {c['node']}  (parent {c.get('parent')})  {c['at']}"
                  f"{'  OVERRIDE: ' + c['override'] if c.get('override') else ''}")
    return 0


def cmd_dataset_impact(settings: Settings, args) -> int:
    settings.need(project=False)
    backend = open_backend(settings.uri)
    name, _, ref = args.ref.partition("@")
    version = resolve_version(backend, check_dataset_name(name), ref)
    print(f"Results built on versions of {name} before {version}:")
    return 1 if print_impact(backend, name, version) and args.strict else 0


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
    for d in m.get("datasets", []):
        w = d.get("window")
        print(f"  dataset {d['dataset']} {d['version']} at {d['mount']}" + (f", window {w['window']} ({w['class']})" if w else ""))
    if m.get("evidence"):
        print(f"  evidence: {m['evidence']['class']}")
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
            ds_hexes = set()
            for d in m.get("datasets", []):
                record, digest = load_version(backend, d["dataset"], d["version"])
                if digest != d["sha256"]:
                    raise VaultError(f"dataset {d['dataset']} {d['version']} hashes to {digest[:12]}, "
                                     f"not the {d['sha256'][:12]} the capsule recorded")
                ds_hexes |= {e["sha256"] for e in record["files"].values()}
            gone_data = backend.missing_blobs(ds_hexes)
            if gone_data:
                raise VaultError(f"{len(gone_data)} of the datasets' {len(ds_hexes)} files are missing")
            hexes |= ds_hexes
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


RESULT_STATUSES = ("validated", "ineffective", "contested", "completed", "tested", "partially_tested", "backtested",
                   "holdout_passed", "forward_testing", "retired")


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
        p.add_argument("--dataset", action="append",
                       help="A registered dataset the run reads, name@version:mount[:window], e.g. "
                            "stocks-eod@latest:data/eod:holdout-2023 (repeatable)")
        p.add_argument("--exploratory", action="store_true",
                       help="Mark the test exploratory: it may use any data, and never validates a node")
        p.add_argument("--override-holdout", metavar="REASON",
                       help="Look at a sealed holdout again; a person confirms at a terminal, and the reason is recorded")
        p.add_argument("--dry-run", action="store_true",
                       help="Check everything the capture needs and print the plan; run, tag and upload nothing")
        p.add_argument("--runtime", help="The runtime the run must match (default: the one the node fixes)")
        p.add_argument("--tool", help="The agent platform making the run (default: VAULT_AGENT_TOOL, or detected)")

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
    p.add_argument("--setup", choices=["uv", "venv", "none"],
                   help="uv: the project's uv.lock in the runtime's Python (the default for a capsule with a "
                        "runtime); venv: a fresh virtual environment from the capsule's lock (the default "
                        "otherwise); none: this interpreter as it is, to retest against what has changed")
    p.add_argument("--tool", help="The agent platform making the replay (default: VAULT_AGENT_TOOL, or detected)")
    p.add_argument("--upgrade", metavar="DIR",
                   help="A regression test: replay the capsule's code with the pyproject.toml and uv.lock in DIR "
                        "(a checkout where `uv lock --upgrade` was run), and compare")
    p.add_argument("--runtime", help="The runtime to check the replay against (default: the capsule's); with "
                                     "--upgrade, the runtime defined from the upgraded environment")
    p.add_argument("--python", help="The base interpreter (default: this one)")
    p.add_argument("--pip", action="append", help="A requirement to install over the lock, e.g. numpy==2.1.0 (repeatable)")
    p.add_argument("--rtol", type=float)
    p.add_argument("--atol", type=float)
    p.add_argument("--note")
    p.add_argument("--agent")
    p.add_argument("--work-item")
    p.add_argument("--no-record", action="store_true", help="Do not keep the replay as a retest capsule")
    p.add_argument("--no-link", action="store_true", help="Do not record the retest on the DAG node")
    p = sub.add_parser("parity", help="Whether a capsule was replayed identically on another machine in its runtime")
    p.add_argument("capsule")
    p.add_argument("--node")
    p = sub.add_parser("runtime", help="Define, show and check runtimes: the machine type, Python and settings "
                                       "a node's evidence runs must match")
    rsub = p.add_subparsers(dest="runtime_command", required=True)
    q = rsub.add_parser("create", help="Define a runtime from an interpreter, once")
    q.add_argument("name")
    q.add_argument("--python", required=True, help="The interpreter to pin, ideally uv-managed (uv python find <v>)")
    q.add_argument("--profile", default="cpu-deterministic-v1", help="The determinism settings: " + ", ".join(PROFILES))
    q.add_argument("--rtol", type=float, default=0.0, help="Relative tolerance of a replay (default 0: exact)")
    q.add_argument("--atol", type=float, default=0.0, help="Absolute tolerance of a replay (default 0: exact)")
    q.add_argument("--no-parity", action="store_true",
                   help="Do not require an identical replay on another machine before a result counts")
    q.add_argument("--note")
    q = rsub.add_parser("show", help="One runtime, or every runtime")
    q.add_argument("name", nargs="?")
    q = rsub.add_parser("check", help="Whether this machine and environment match a runtime")
    q.add_argument("name")
    q.add_argument("--python", help="The interpreter to check (default: this one)")
    q.add_argument("--cwd", default=".", help="The project (default: here)")
    q.add_argument("--tool")
    p = sub.add_parser("coverage", help="List the DAG's result nodes that have no capsule")
    p.add_argument("--verify", action="store_true", help="Also check every recorded capsule is intact")
    p.add_argument("--strict", action="store_true", help="Exit 1 when any result node has no capsule")
    p = sub.add_parser("dataset", help="Register, version and fetch datasets, and define their windows")
    dsub = p.add_subparsers(dest="dataset_command", required=True)
    q = dsub.add_parser("create", help="Register a dataset")
    q.add_argument("name")
    q.add_argument("--rule", choices=DATASET_RULES, required=True,
                   help="append-only: only add files or extend them at the end; revisable: changes are revisions; "
                        "frozen: one version only")
    q.add_argument("--title")
    q.add_argument("--description")
    q.add_argument("--source", action="append", help="Where the data comes from: a URL, an API, a vendor (repeatable)")
    q.add_argument("--licence")
    q.add_argument("--owner")
    q.add_argument("--agent")
    q = dsub.add_parser("add", help="Add a version from a folder, checking the dataset's rule")
    q.add_argument("name")
    q.add_argument("--from", dest="source_folder", required=True, help="The folder holding the whole dataset")
    q.add_argument("--note")
    q.add_argument("--source", help="Where this version's data came from, and when")
    q.add_argument("--fetched-by", help="The script or command that fetched it, ideally with its commit")
    q.add_argument("--source-checksums", help="A file of checksums the source publishes, kept with the version")
    q.add_argument("--revise", metavar="REASON", help="Change or remove data: a revision, which a person confirms")
    q.add_argument("--allow-append-only-revision", action="store_true",
                   help="With --revise, revise an append-only dataset")
    q.add_argument("--agent")
    q = dsub.add_parser("window", help="Define a named window: backtest, sealed holdout, or forward")
    q.add_argument("name")
    q.add_argument("window")
    q.add_argument("--class", dest="cls", choices=WINDOW_CLASSES, required=True)
    q.add_argument("--from-date", help="Start of a backtest or holdout window, as the data's own dates")
    q.add_argument("--to-date", help="End of a backtest or holdout window")
    q.add_argument("--from-version", help="A forward window: the data added after this version")
    q.add_argument("--note")
    dsub.add_parser("list", help="List datasets")
    q = dsub.add_parser("show", help="A dataset's description, versions and windows, or one version")
    q.add_argument("ref", help="name, or name@version")
    q.add_argument("--files", action="store_true", help="List every file of the version")
    q = dsub.add_parser("diff", help="What changed between two versions")
    q.add_argument("a")
    q.add_argument("b")
    q = dsub.add_parser("fetch", help="Fetch a version, hash-checked, into the cache or a folder")
    q.add_argument("ref", help="name@version, or name for the latest")
    q.add_argument("--to")
    q = dsub.add_parser("uses", help="Which capsules used a dataset, and who looked at a holdout")
    q.add_argument("name")
    q.add_argument("--window")
    q = dsub.add_parser("impact", help="The results built on versions before this one")
    q.add_argument("ref", help="name@version")
    q.add_argument("--strict", action="store_true", help="Exit 1 when there are any")
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
        if args.command_name == "dataset":
            return {"create": cmd_dataset_create, "add": cmd_dataset_add, "window": cmd_dataset_window,
                    "list": cmd_dataset_list, "show": cmd_dataset_show, "diff": cmd_dataset_diff,
                    "fetch": cmd_dataset_fetch, "uses": cmd_dataset_uses,
                    "impact": cmd_dataset_impact}[args.dataset_command](settings, args)
        if args.command_name == "parity":
            return cmd_parity(settings, args)
        if args.command_name == "runtime":
            return {"create": cmd_runtime_create, "show": cmd_runtime_show,
                    "check": cmd_runtime_check}[args.runtime_command](settings, args)
        if args.command_name == "lifecycle":
            return cmd_lifecycle(settings, args)
    except VaultError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
