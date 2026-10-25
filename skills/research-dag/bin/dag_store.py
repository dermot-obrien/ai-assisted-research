#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""
The shared, event-sourced store for the hypothesis DAG.

The store is a git repository, usually private, with one folder per project.
Every change to a DAG is one new, never-edited JSON event file, so any number
of machines and agents can pull, write and push without a merge conflict. The
DAG is derived by replaying the events in time order, and `hypothesis-dag.yaml`
becomes a generated view of that replay, so every tool that reads the YAML
keeps working unchanged.

    <store>/README.md                          the format, for a reader without this tool
    <store>/<project>/events/YYYY-MM-DD/*.json one event per file
    <store>/<project>/archive/*.jsonl          closed history pruned out of events/

A workspace opts in with two keys in research.yaml:

    dag_store: "git@example.com:me/research-dags.git"   # clone path or URL
    dag_project: "my-project"                           # folder in the store

Without them every tool behaves exactly as before, on the plain YAML file.

Usage:
    python <skills>/research-dag/bin/dag_store.py init
    python <skills>/research-dag/bin/dag_store.py import [--from research/hypothesis-dag.yaml]
    python <skills>/research-dag/bin/dag_store.py view
    python <skills>/research-dag/bin/dag_store.py report [--json]
    python <skills>/research-dag/bin/dag_store.py record
    python <skills>/research-dag/bin/dag_store.py prune [--days 90] [--dry-run]
    python <skills>/research-dag/bin/dag_store.py verify --against <file.yaml>
    python <skills>/research-dag/bin/dag_store.py sync

Every command also takes --store and --project, which override research.yaml.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

EVENT_TYPES = ("doc", "add", "update", "append", "alias")
DEFAULT_CLOSED = ("discarded", "ineffective", "validated")
PROJECT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_MISSING = object()

STORE_README = """# Research DAGs

Hypothesis DAGs shared across machines, tools and agents, one folder per project.
Written by the research-dag skill (`dag_update.py`, `dag_store.py`); nothing here is edited by hand.

## Format (for an agent without the skill)

Each change is one new JSON file, `<project>/events/YYYY-MM-DD/<utc-stamp>-<host>-<hex>[-NNNN].json`.
Never edit an existing event: write a new one, commit, `git pull --rebase`, push. Events are new
files, so a rebase cannot conflict.

`<project>/archive/<utc-stamp>-<host>-<hex>.jsonl` holds closed history pruned out of `events/`,
one event per line with `src` (the path it had under the project folder). Archives are never
edited. The DAG is `events/` and every archive replayed together, de-duplicated by `src`, in
(`ts`, `src`) order.

| type | fields |
|---|---|
| `doc` | `fields` (top-level keys other than `nodes`), optional `order` (top-level key order), `header` (the file's leading comment), `comments` (key to the comment above it), `unset` |
| `add` | `id`, `node` (the whole node, fields in order), optional `comment` (the comment above it) |
| `update` | `id`, `set` (field to new value), `prev` (field to the value the writer saw), optional `unset` |
| `append` | `id`, `field`, `values` (items appended to a list field, skipping ones already there) |
| `alias` | `id` (the id the node goes by), `was` (the id it was added as), `target` (the `eid` of that `add`) |

Every event also carries `eid` (its file name without `.json`), `ts` (ISO-8601 UTC) and `host`.
The latest `set` of a field wins. When its `prev` differs from the value replay holds, two writers
changed the field concurrently, and the replaced value is reported. Two `add` events with the
same `id`: the earlier keeps it, the later one goes by the id its `alias` names, or, with no
alias recorded, the id with the next free letter suffix.

Values YAML has and JSON lacks are tagged: `{"$date": "2026-01-31"}`, `{"$datetime": "..."}`,
and `{"$map": [[key, value], ...]}` for a mapping whose keys are not all strings.
"""


def warn(msg: str) -> None:
    print(f"dag_store: {msg}", file=sys.stderr)


class StoreError(RuntimeError):
    pass


# ---------------------------------------------------------------- values

def encode(value: Any) -> Any:
    """A YAML value as JSON, tagging what JSON cannot hold."""
    if isinstance(value, dt.datetime):
        return {"$datetime": value.isoformat()}
    if isinstance(value, dt.date):
        return {"$date": value.isoformat()}
    if isinstance(value, dict):
        if all(isinstance(k, str) for k in value):
            return {k: encode(v) for k, v in value.items()}
        return {"$map": [[encode(k), encode(v)] for k, v in value.items()]}
    if isinstance(value, (list, tuple)):
        return [encode(v) for v in value]
    return value


def decode(value: Any) -> Any:
    if isinstance(value, dict):
        if len(value) == 1:
            (k, v), = value.items()
            if k == "$date":
                return dt.date.fromisoformat(v)
            if k == "$datetime":
                return dt.datetime.fromisoformat(v)
            if k == "$map":
                return {_hashable(decode(a)): decode(b) for a, b in v}
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def _hashable(v: Any) -> Any:
    return tuple(v) if isinstance(v, list) else v


def short(value: Any, limit: int = 160) -> str:
    text = json.dumps(encode(value), ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 3] + "..."


# ---------------------------------------------------------------- git

def git(args: list[str], cwd: Path) -> str:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise StoreError((r.stderr or r.stdout).strip() or f"git {' '.join(args)} failed")
    return r.stdout.strip()


def try_git(args: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        return True, git(args, cwd)
    except StoreError as e:
        return False, str(e)


def looks_remote(spec: str) -> bool:
    return "://" in spec or bool(re.match(r"^[\w.-]+@[\w.-]+:", spec))


def is_work_tree(path: Path) -> bool:
    return (path / ".git").exists()


def is_bare_repo(path: Path) -> bool:
    return (path / "HEAD").is_file() and (path / "objects").is_dir() and not is_work_tree(path)


def default_home() -> Path:
    env = os.environ.get("RESEARCH_DAG_HOME")
    return Path(env).expanduser() if env else Path.home() / ".research-dags"


def host_name() -> str:
    return re.sub(r"[^a-z0-9-]", "", socket.gethostname().lower())[:20] or "host"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class FileLock:
    """An exclusive lock on the local clone, held for one read-modify-write."""

    def __init__(self, path: Path, tries: int = 40, wait: float = 0.5):
        self.path, self.tries, self.wait = path, tries, wait

    def __enter__(self):
        for _ in range(self.tries):
            try:
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return self
            except FileExistsError:
                time.sleep(self.wait)
        raise TimeoutError(f"Could not acquire the store lock at {self.path}. "
                           f"Another process may be writing; delete it if none is.")

    def __exit__(self, *exc):
        os.close(self.fd)
        try:
            os.remove(self.path)
        except OSError:
            pass


# ---------------------------------------------------------------- replay

class State:
    """A DAG replayed from events, with what replay noticed on the way."""

    def __init__(self):
        self.header: str | None = None
        self.doc_comments: dict[str, str] = {}
        self.node_comments: dict[str, str] = {}
        self.order: list[str] = []          # top-level key order
        self.doc: dict[str, Any] = {}       # top-level keys other than nodes
        self.nodes: dict[str, dict] = {}    # id -> node, in the order added
        self.aliases: list[dict] = []
        self.conflicts: list[dict] = []
        self.orphans: list[dict] = []       # events naming a node replay does not have
        self.sources: dict[str, list[str]] = {}
        self.last_ts: dict[str, str] = {}
        self.add_ids: dict[str, str] = {}   # add eid -> id the node goes by
        self.add_was: dict[str, str] = {}   # add eid -> id it was added as
        self.setters: dict[tuple[str, str], dict] = {}

    def to_dag(self) -> dict:
        out: dict[str, Any] = {}
        order = list(self.order) or list(self.doc) + ["nodes"]
        for key in [*order, *[k for k in self.doc if k not in order]]:
            if key == "nodes":
                out["nodes"] = copy.deepcopy(list(self.nodes.values()))
            elif key in self.doc:
                out[key] = copy.deepcopy(self.doc[key])
        if "nodes" not in out:
            out["nodes"] = copy.deepcopy(list(self.nodes.values()))
        return out


def next_suffix(base: str, taken: Iterable[str]) -> str:
    taken = set(taken)
    for letter in "bcdefghijklmnopqrstuvwxyz":
        if base + letter not in taken:
            return base + letter
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


def replay(events: list[dict]) -> State:
    st = State()
    recorded = {e["target"]: e for e in events if e.get("type") == "alias" and e.get("target")}
    # Every id an add or a recorded alias names is taken for the letter suffixes.
    taken = {e.get("id") for e in events if e.get("type") in ("add", "alias")}

    def touch(nid: str, ev: dict) -> None:
        st.sources.setdefault(nid, []).append(ev["_src"])
        st.last_ts[nid] = max(st.last_ts.get(nid, ""), ev.get("ts", ""))

    for ev in events:
        kind = ev.get("type")
        if kind == "doc":
            if ev.get("header") is not None:
                st.header = ev["header"]
            st.doc_comments.update(ev.get("comments") or {})
            if ev.get("order"):
                st.order = list(ev["order"])
            for k, v in (ev.get("fields") or {}).items():
                st.doc[k] = decode(v)
            for k in ev.get("unset") or []:
                st.doc.pop(k, None)
        elif kind == "add":
            was = ev["id"]
            alias = recorded.get(ev.get("eid"))
            nid = alias["id"] if alias else was
            if nid in st.nodes:
                nid = next_suffix(was, set(st.nodes) | taken)
                taken.add(nid)
                st.aliases.append({"id": nid, "was": was, "eid": ev.get("eid"), "ts": ev.get("ts"),
                                   "host": ev.get("host"), "recorded": False})
            elif alias:
                st.aliases.append({"id": nid, "was": was, "eid": ev.get("eid"), "ts": alias.get("ts"),
                                   "host": alias.get("host"), "recorded": True})
            node = decode(ev.get("node") or {})
            node = {k: (nid if k == "id" else v) for k, v in node.items()} if "id" in node \
                else {"id": nid, **node}
            st.nodes[nid] = node
            if ev.get("comment"):
                st.node_comments[nid] = ev["comment"]
            st.add_ids[ev.get("eid")] = nid
            st.add_was[ev.get("eid")] = was
            touch(nid, ev)
        elif kind in ("update", "append"):
            nid = ev.get("id")
            node = st.nodes.get(nid)
            if node is None:
                st.orphans.append({"eid": ev.get("eid"), "type": kind, "id": nid})
                continue
            if kind == "update":
                prev = ev.get("prev") or {}
                for field, raw in (ev.get("set") or {}).items():
                    value = decode(raw)
                    current = node.get(field)
                    if field in prev and decode(prev[field]) != current and value != current:
                        earlier = st.setters.get((nid, field), {})
                        st.conflicts.append({
                            "id": nid, "field": field, "replaced": current, "value": value,
                            "ts": ev.get("ts"), "host": ev.get("host"), "eid": ev.get("eid"),
                            "replaced_ts": earlier.get("ts"), "replaced_host": earlier.get("host"),
                        })
                    if field == "id":
                        continue
                    node[field] = value
                    st.setters[(nid, field)] = {"ts": ev.get("ts"), "host": ev.get("host")}
                for field in ev.get("unset") or []:
                    if field != "id":
                        node.pop(field, None)
            else:
                field = ev.get("field")
                items = node.get(field)
                if not isinstance(items, list):
                    items = [] if items is None else [items]
                for v in decode(ev.get("values") or []):
                    if v not in items:
                        items.append(v)
                node[field] = items
            touch(nid, ev)
    # Alias events belong to the node they name, for pruning.
    for ev in events:
        if ev.get("type") == "alias" and ev.get("id") in st.nodes:
            touch(ev["id"], ev)
    return st


# ---------------------------------------------------------------- diff

def iter_nodes(dag: dict) -> list[dict]:
    return list((dag or {}).get("nodes") or [])


def diff_events(before: dict, after: dict) -> list[dict]:
    """The events that turn `before` into `after`. Nodes cannot be removed."""
    events: list[dict] = []
    doc_set = {k: encode(v) for k, v in after.items()
               if k != "nodes" and (k not in before or before[k] != v)}
    doc_unset = [k for k in before if k != "nodes" and k not in after]
    if doc_set or doc_unset or list(before) != list(after):
        ev: dict[str, Any] = {"type": "doc", "fields": doc_set}
        if list(before) != list(after):
            ev["order"] = list(after)
        if doc_unset:
            ev["unset"] = doc_unset
        events.append(ev)

    old = {n["id"]: n for n in iter_nodes(before)}
    new_ids = [n["id"] for n in iter_nodes(after)]
    gone = [i for i in old if i not in set(new_ids)]
    if gone:
        raise StoreError(f"nodes cannot be removed from the DAG store: {', '.join(gone)}")

    for node in iter_nodes(after):
        nid = node["id"]
        if nid not in old:
            events.append({"type": "add", "id": nid, "node": encode(node)})
    for node in iter_nodes(after):
        nid = node["id"]
        if nid not in old:
            continue
        was = old[nid]
        sets: dict[str, Any] = {}
        prev: dict[str, Any] = {}
        for field, value in node.items():
            if field in was and was[field] == value:
                continue
            before_value = was.get(field)
            # Growing a list (or starting one) is an append, so concurrent appends all survive.
            if before_value is None and isinstance(value, list) and value:
                before_value = []
            if (isinstance(before_value, list) and isinstance(value, list)
                    and len(value) > len(before_value) and value[: len(before_value)] == before_value):
                events.append({"type": "append", "id": nid, "field": field,
                               "values": encode(value[len(before_value):])})
                continue
            sets[field] = encode(value)
            prev[field] = encode(before_value)
        unset = [f for f in was if f not in node]
        if sets or unset:
            ev = {"type": "update", "id": nid, "set": sets, "prev": prev}
            if unset:
                ev["unset"] = unset
            events.append(ev)
    return events


# ---------------------------------------------------------------- view

VIEW_BANNER = "# Generated from the shared DAG store, project {project}. Do not edit by hand:"


class _ViewDumper(yaml.SafeDumper):
    """Multi-line text as literal blocks, so notes read as they were written."""


def _str_representer(dumper, value):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_ViewDumper.add_representer(str, _str_representer)


def dump_yaml(data: Any) -> str:
    return yaml.dump(data, Dumper=_ViewDumper, sort_keys=False, allow_unicode=True,
                     default_flow_style=False, width=1_000_000)


def _indent(text: str, by: str = "  ") -> str:
    return "".join(by + line if line.strip() else line for line in text.splitlines(keepends=True))


def render_view(state: State, project: str, commit: str | None = None) -> str:
    """The DAG as YAML, with its comments, and concurrent edits and aliases shown as comments."""

    lines = [VIEW_BANNER.format(project=project),
             "# change it with dag_update.py; dag_store.py view regenerates it.",
             f"# dag-store-commit: {commit or 'none'}"]
    out = "\n".join(lines) + "\n"
    if state.header:
        out += "#\n" + state.header.rstrip("\n") + "\n"
    out += "\n"

    notes: dict[str, list[str]] = {}
    for c in state.conflicts:
        notes.setdefault(c["id"], []).append(
            f"# concurrent edit: {c['field']} was {short(c['replaced'])}"
            f" ({c.get('replaced_host') or '?'} {c.get('replaced_ts') or '?'}),"
            f" replaced by {short(c['value'])} ({c.get('host')} {c.get('ts')})")
    for a in state.aliases:
        how = "recorded" if a["recorded"] else "not yet recorded"
        notes.setdefault(a["id"], []).append(
            f"# alias: added as {a['was']} by a concurrent writer; renamed {a['id']} ({how})")

    dag = state.to_dag()
    for key, value in dag.items():
        if state.doc_comments.get(key):
            out += state.doc_comments[key].rstrip("\n") + "\n"
        if key != "nodes":
            out += dump_yaml({key: value}) + "\n"
            continue
        out += "nodes:\n"
        for node in value:
            comment = state.node_comments.get(node["id"])
            if comment:
                out += comment.rstrip("\n") + "\n"
            for note in notes.get(node["id"], []):
                out += "  " + note.replace("\n", " ") + "\n"
            out += _indent(dump_yaml([node]))
            out += "\n"
    return out.rstrip("\n") + "\n"


def view_commit(text: str) -> str | None:
    m = re.search(r"^# dag-store-commit: ([0-9a-f]{7,40})$", text, re.MULTILINE)
    return m.group(1) if m else None


TOP_KEY = re.compile(r"^([A-Za-z_][\w.-]*)\s*:")
NODE_START = re.compile(r"^\s*-\s+id:\s*['\"]?([^'\"\s#]+)")


def extract_comments(text: str) -> tuple[dict[str, str], dict[str, str]]:
    """The comment blocks that lead each top-level key and each node, verbatim.

    Comments are not content, so the events keep them beside it: a block of
    comment lines directly above a top-level key or a node's `- id:` line goes
    with that key or node, and the view writes it back in the same place. The
    file's leading block is the header (split_header). Comments elsewhere, such
    as between a node's fields, are not kept.
    """
    doc: dict[str, str] = {}
    nodes: dict[str, str] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines) and (lines[i].startswith("#") or not lines[i].strip()):
        i += 1
    pending: list[str] = []
    for line in lines[i:]:
        stripped = line.strip()
        if stripped.startswith("#"):
            pending.append(line.rstrip())
            continue
        if not stripped:
            if pending:
                pending.append("")
            continue
        block = "\n".join(pending).strip("\n")
        pending = []
        if not block:
            continue
        m = TOP_KEY.match(line)
        if m:
            doc[m.group(1)] = block
            continue
        m = NODE_START.match(line)
        if m:
            nodes[m.group(1)] = block
    return doc, nodes


def split_header(text: str) -> str | None:
    """The comment block at the top of a YAML file, verbatim."""
    header = []
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            header.append(line)
        else:
            break
    while header and not header[-1].strip():
        header.pop()
    while header and not header[0].strip():
        header.pop(0)
    return "\n".join(header) if header else None


# ---------------------------------------------------------------- the store

class DagStore:
    """One project's DAG in a local clone of the store."""

    def __init__(self, clone: Path, project: str, remote: str | None = None):
        if not PROJECT_NAME.match(project or ""):
            raise StoreError(f"dag_project must be a plain folder name, got {project!r}")
        self.clone = Path(clone)
        self.project = project
        self.remote = remote
        self.dir = self.clone / project

    # --- location

    @classmethod
    def locate(cls, spec: str, project: str, base: Path | None = None) -> "DagStore":
        """A store from `dag_store`: a clone to use as it is, or a URL or bare repo to clone."""
        spec = str(spec).strip()
        if not looks_remote(spec):
            path = Path(spec).expanduser()
            if not path.is_absolute() and base is not None:
                path = (base / path)
            path = path.resolve()
            if is_work_tree(path):
                return cls(path, project)
            if not is_bare_repo(path):
                raise StoreError(f"dag_store {spec} is neither a clone nor a repository to clone "
                                 f"(resolved to {path})")
            spec = str(path)
        name = re.sub(r"\.git$", "", re.split(r"[/\\:]", spec.rstrip("/\\"))[-1]) or "store"
        return cls(default_home() / name, project, remote=spec)

    @classmethod
    def from_config(cls, cfg, store: str | None = None, project: str | None = None) -> "DagStore":
        spec = store or cfg.dag_store
        proj = project or cfg.dag_project
        if not spec or not proj:
            raise StoreError("research.yaml needs both dag_store and dag_project to use the DAG store")
        return cls.locate(spec, proj, base=cfg.repo_root)

    def ensure(self) -> None:
        if not is_work_tree(self.clone):
            if not self.remote:
                raise StoreError(f"no store clone at {self.clone}")
            self.clone.parent.mkdir(parents=True, exist_ok=True)
            ok, out = try_git(["clone", "--quiet", self.remote, str(self.clone)], self.clone.parent)
            if not ok:
                raise StoreError(f"could not clone {self.remote}:\n{out}")
            if not self.has_commits():
                try_git(["symbolic-ref", "HEAD", "refs/heads/main"], self.clone)
        if not try_git(["config", "user.email"], self.clone)[0]:
            # A bare container may have no git identity; the store should not care.
            git(["config", "user.name", "research-dag"], self.clone)
            git(["config", "user.email", "research-dag@localhost"], self.clone)

    def lock(self) -> FileLock:
        return FileLock(self.clone / ".git" / "research-dag.lock")

    def has_remote(self) -> bool:
        return "origin" in try_git(["remote"], self.clone)[1].split()

    def has_commits(self) -> bool:
        return try_git(["rev-parse", "--verify", "HEAD"], self.clone)[0]

    def head(self) -> str | None:
        ok, out = try_git(["rev-parse", "HEAD"], self.clone)
        return out if ok else None

    # --- sync

    def pull(self) -> bool:
        """Bring the clone up to origin/main. False when the remote was unreachable."""
        if not self.has_remote():
            return True
        ok, out = try_git(["fetch", "--quiet", "origin"], self.clone)
        if not ok:
            warn(f"can't reach the store's remote, working from the local copy ({out.splitlines()[0] if out else ''})")
            return False
        if not try_git(["rev-parse", "--verify", "origin/main"], self.clone)[0]:
            return True  # the remote is still empty
        if not self.has_commits():
            git(["checkout", "--quiet", "-B", "main", "origin/main"], self.clone)
            return True
        ok, out = try_git(["rebase", "--quiet", "origin/main"], self.clone)
        if not ok:
            try_git(["rebase", "--abort"], self.clone)
            warn(f"couldn't rebase onto origin/main ({out.splitlines()[0] if out else ''})")
        return True

    def commit(self, message: str) -> bool:
        git(["add", "-A"], self.clone)
        if try_git(["diff", "--cached", "--quiet"], self.clone)[0]:
            return False
        git(["commit", "--quiet", "-m", message], self.clone)
        return True

    def commit_and_push(self, message: str, on_rebase: Callable[[], None] | None = None,
                        attempts: int = 5) -> bool:
        """Commit what was written and push it, with anything left unpushed before.

        A rejected push means someone else pushed first. Events are new files, so the
        rebase cannot conflict; `on_rebase` then gets a look at the merged events (to
        rename an id a concurrent writer took) before the push is tried again.
        """
        self.commit(message)
        if not self.has_remote():
            return True
        for attempt in range(attempts):
            ok, _ = try_git(["push", "--quiet", "-u", "origin", "HEAD:main"], self.clone)
            if ok:
                return True
            if not self.pull():
                break
            if on_rebase:
                on_rebase()
                self.commit(message + " (after a concurrent push)")
            time.sleep(0.2 * attempt)
        warn("NOT PUSHED: recorded locally only. It goes up with the next successful write or dag_store.py sync.")
        return False

    # --- events

    def _read_live(self) -> list[dict]:
        out = []
        root = self.dir / "events"
        if not root.is_dir():
            return out
        for path in sorted(root.rglob("*.json")):
            try:
                ev = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                warn(f"skipping unreadable event {path}")
                continue
            ev["_src"] = path.relative_to(self.dir).as_posix()
            out.append(ev)
        return out

    def _read_archive(self) -> list[dict]:
        out = []
        root = self.dir / "archive"
        if not root.is_dir():
            return out
        for path in sorted(root.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    warn(f"skipping unreadable line in {path.name}")
                    continue
                ev["_src"] = ev.pop("src")
                ev["_archived"] = True
                out.append(ev)
        return out

    def events(self) -> list[dict]:
        """Live and archived events, de-duplicated by original path, in (ts, src) order."""
        seen: set[str] = set()
        out = []
        for ev in [*self._read_live(), *self._read_archive()]:
            if ev["_src"] in seen:
                continue
            seen.add(ev["_src"])
            out.append(ev)
        return sorted(out, key=lambda e: (e.get("ts", ""), e["_src"]))

    def replay(self) -> State:
        return replay(self.events())

    def has_events(self) -> bool:
        return any((self.dir / "events").rglob("*.json")) or any((self.dir / "archive").glob("*.jsonl"))

    def write_events(self, bodies: list[dict]) -> list[dict]:
        """Write each body as a new event file, sharing one timestamp, in order."""
        if not bodies:
            return []
        ts = utc_now()
        host = host_name()
        stamp = re.sub(r"[-:]", "", ts).split(".")[0] + "Z"
        day = dt.date.today().isoformat()
        folder = self.dir / "events" / day
        folder.mkdir(parents=True, exist_ok=True)
        batch = f"{stamp}-{host}-{secrets.token_hex(3)}"
        written = []
        for i, body in enumerate(bodies, 1):
            eid = batch if len(bodies) == 1 else f"{batch}-{i:04d}"
            ev = {"eid": eid, "ts": ts, "host": host, **body}
            path = folder / f"{eid}.json"
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(ev, indent=2, ensure_ascii=False) + "\n")
            written.append({**ev, "_src": path.relative_to(self.dir).as_posix()})
        return written

    def init_files(self) -> None:
        readme = self.clone / "README.md"
        if not readme.exists() or readme.read_text(encoding="utf-8") != STORE_README:
            with open(readme, "w", encoding="utf-8", newline="\n") as f:
                f.write(STORE_README)
        keep = self.dir / "events" / ".gitkeep"
        keep.parent.mkdir(parents=True, exist_ok=True)
        if not keep.exists():
            keep.write_text("", encoding="utf-8")

    # --- concurrent ids

    def resolve_collisions(self, own: list[dict]) -> list[dict]:
        """Rename our new nodes whose id a concurrent writer took first.

        The node already in the store keeps the id; ours takes the next free letter
        suffix, and an alias event records it so every replay agrees.
        """
        adds = [e for e in own if e.get("type") == "add"]
        if not adds:
            return []
        own_eids = {e["eid"] for e in adds}
        state = self.replay()
        events = self.events()
        recorded = {e.get("target") for e in events if e.get("type") == "alias"}
        # Ids other writers' adds hold: added as, and not renamed away by an alias.
        others = {was for eid, was in state.add_was.items() if eid not in own_eids and eid not in recorded}
        # Ids events name, not the suffixes replay gave unrecorded duplicates, ours among them.
        taken = {e["id"] for e in events if e.get("type") in ("add", "alias")}
        bodies = []
        renamed: dict[str, str] = {}
        for ev in adds:
            if ev["eid"] in recorded or ev["id"] not in others:
                continue
            new_id = next_suffix(ev["id"], taken)
            taken.add(new_id)
            renamed[ev["id"]] = new_id
            bodies.append({"type": "alias", "id": new_id, "was": ev["id"], "target": ev["eid"]})
        # Our appends named the old id (a parent's avenues); append the new one too.
        # The old id stays listed, since the other writer's node holds it.
        for ev in own:
            if ev.get("type") != "append":
                continue
            values = [renamed[v] for v in decode(ev.get("values") or []) if isinstance(v, str) and v in renamed]
            if values:
                bodies.append({"type": "append", "id": ev["id"], "field": ev["field"], "values": values})
        return self.write_events(bodies)

    # --- views

    def write_view(self, path: Path, state: State | None = None) -> bool:
        state = state or self.replay()
        text = render_view(state, self.project, self.head())
        path = Path(path)
        if path.exists():
            with open(path, encoding="utf-8", newline="") as f:
                old = f.read()
            if re.sub(r"^# dag-store-commit: .*$", "", old, flags=re.M) == \
                    re.sub(r"^# dag-store-commit: .*$", "", text, flags=re.M) and view_commit(old):
                return False
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return True

    def replay_at(self, commit: str) -> State:
        """The project replayed as it stood at one commit of the store."""
        prefix = f"{self.project}/"
        listing = git(["ls-tree", "-r", "--name-only", commit, "--", prefix], self.clone)
        live, archived = [], []
        for name in listing.splitlines():
            rel = name[len(prefix):]
            if rel.startswith("events/") and rel.endswith(".json"):
                ev = json.loads(git(["show", f"{commit}:{name}"], self.clone))
                ev["_src"] = rel
                live.append(ev)
            elif rel.startswith("archive/") and rel.endswith(".jsonl"):
                for line in git(["show", f"{commit}:{name}"], self.clone).splitlines():
                    if line.strip():
                        ev = json.loads(line)
                        ev["_src"] = ev.pop("src")
                        archived.append(ev)
        seen, out = set(), []
        for ev in [*live, *archived]:
            if ev["_src"] not in seen:
                seen.add(ev["_src"])
                out.append(ev)
        return replay(sorted(out, key=lambda e: (e.get("ts", ""), e["_src"])))

    # --- prune

    def closed_nodes(self, state: State, days: float, statuses: Iterable[str]) -> list[str]:
        cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat().replace("+00:00", "Z")
        statuses = set(statuses)
        return [nid for nid, node in state.nodes.items()
                if node.get("status") in statuses and state.last_ts.get(nid, "") < cutoff]

    def archive(self, node_ids: list[str], state: State) -> dict | None:
        """Move the given nodes' live events into one new archive file."""
        live = {e["_src"]: e for e in self._read_live()}
        moving = []
        for nid in node_ids:
            for src in state.sources.get(nid, []):
                if src in live:
                    moving.append(live.pop(src))
        if not moving:
            return None
        moving.sort(key=lambda e: (e.get("ts", ""), e["_src"]))
        stamp = re.sub(r"[-:]", "", utc_now()).split(".")[0] + "Z"
        name = f"{stamp}-{host_name()}-{secrets.token_hex(3)}.jsonl"
        folder = self.dir / "archive"
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / name, "w", encoding="utf-8", newline="\n") as f:
            for ev in moving:
                body = {k: v for k, v in ev.items() if not k.startswith("_")}
                f.write(json.dumps({"src": ev["_src"], **body}, ensure_ascii=False) + "\n")
        for ev in moving:
            (self.dir / ev["_src"]).unlink()
        return {"file": f"{self.project}/archive/{name}", "nodes": len(node_ids), "events": len(moving)}


# ---------------------------------------------------------------- comparison

def compare(a: dict, b: dict) -> list[str]:
    """Differences in content between two DAGs, including node and field order."""
    problems = []
    if list(a) != list(b):
        problems.append(f"top-level keys differ: {list(a)} vs {list(b)}")
    for key in set(a) | set(b):
        if key != "nodes" and a.get(key) != b.get(key):
            problems.append(f"top-level {key} differs")
    na, nb = iter_nodes(a), iter_nodes(b)
    ids_a, ids_b = [n.get("id") for n in na], [n.get("id") for n in nb]
    if ids_a != ids_b:
        problems.append(f"node order differs ({len(ids_a)} vs {len(ids_b)} nodes)")
    for x, y in zip(na, nb):
        if x != y:
            fields = sorted({k for k in set(x) | set(y) if x.get(k, _MISSING) != y.get(k, _MISSING)})
            problems.append(f"{x.get('id')}: {', '.join(fields) or 'values'} differ")
        elif list(x) != list(y):
            problems.append(f"{x.get('id')}: field order differs")
    return problems


def import_dag(store: DagStore, source: Path) -> list[dict]:
    """Seed a project from an existing hypothesis-dag.yaml: one event per node."""
    text = Path(source).read_text(encoding="utf-8")
    dag = yaml.safe_load(text) or {}
    if not isinstance(dag.get("nodes"), list):
        raise StoreError(f"{source} has no nodes list")
    doc_comments, node_comments = extract_comments(text)
    bodies: list[dict] = [{
        "type": "doc",
        "header": split_header(text),
        "order": list(dag),
        "fields": {k: encode(v) for k, v in dag.items() if k != "nodes"},
        "comments": doc_comments,
    }]
    seen = set()
    for node in dag["nodes"]:
        if not isinstance(node, dict) or not node.get("id"):
            raise StoreError(f"{source} has a node with no id")
        if node["id"] in seen:
            raise StoreError(f"{source} has the id {node['id']} twice")
        seen.add(node["id"])
        body = {"type": "add", "id": node["id"], "node": encode(node)}
        if node_comments.get(node["id"]):
            body["comment"] = node_comments[node["id"]]
        bodies.append(body)
    return store.write_events(bodies)


# ---------------------------------------------------------------- CLI

def _config():
    try:
        import rms_config
        return rms_config.load()
    except FileNotFoundError:
        return None


def open_store(args) -> tuple[DagStore, Any]:
    cfg = _config()
    if cfg is None and not (args.store and args.project):
        raise StoreError("no research.yaml found; pass --store and --project")
    if cfg is None:
        store = DagStore.locate(args.store, args.project, base=Path.cwd())
    else:
        store = DagStore.from_config(cfg, args.store, args.project)
    store.ensure()
    return store, cfg


def view_path(args, cfg) -> Path | None:
    if getattr(args, "view", None):
        return Path(args.view)
    return cfg.dag_path if cfg is not None else None


def cmd_init(args) -> int:
    store, _ = open_store(args)
    with store.lock():
        store.pull()
        store.init_files()
        store.commit_and_push(f"init {store.project}")
    print(f"DAG store ready: {store.clone} (project {store.project})")
    return 0


def cmd_import(args) -> int:
    store, cfg = open_store(args)
    source = Path(args.source) if args.source else (cfg.dag_path if cfg else None)
    if source is None or not source.is_file():
        raise StoreError(f"no DAG to import at {source}")
    with store.lock():
        store.pull()
        if store.has_events():
            raise StoreError(f"project {store.project} already has events; import seeds an empty project only")
        store.init_files()
        written = import_dag(store, source)
        state = store.replay()
        problems = compare(state.to_dag(), yaml.safe_load(source.read_text(encoding="utf-8")))
        if problems:
            for ev in written:
                (store.dir / ev["_src"]).unlink(missing_ok=True)
            for p in problems[:20]:
                print(f"  {p}")
            raise StoreError("replay does not reproduce the imported DAG; nothing was committed")
        pushed = store.commit_and_push(f"import {store.project}: {len(written) - 1} nodes from {source.name}")
    print(f"Imported {len(written) - 1} nodes into {store.project} ({len(written)} events); "
          f"replay reproduces {source}. {'Pushed.' if pushed else ''}".rstrip())
    print("Next: set dag_store and dag_project in research.yaml, then dag_store.py view.")
    return 0


def cmd_view(args) -> int:
    store, cfg = open_store(args)
    target = view_path(args, cfg)
    if target is None:
        raise StoreError("where should the view go? pass --view <path>")
    with store.lock():
        store.pull()
        state = store.replay()
        changed = store.write_view(target, state)
    print(f"{'Wrote' if changed else 'Unchanged:'} {target} ({len(state.nodes)} nodes)")
    _print_findings(state)
    return 0


def _print_findings(state: State) -> None:
    if state.conflicts:
        print(f"{len(state.conflicts)} concurrent edit(s); the later value won:")
        for c in state.conflicts:
            print(f"  {c['id']} {c['field']}: {short(c['replaced'], 80)} replaced by {short(c['value'], 80)}"
                  f" ({c.get('host')} {c.get('ts')})")
    if state.aliases:
        print(f"{len(state.aliases)} alias(es) from concurrent adds:")
        for a in state.aliases:
            print(f"  {a['id']} was added as {a['was']}{'' if a['recorded'] else ' (not yet recorded)'}")
    if state.orphans:
        print(f"{len(state.orphans)} event(s) name a node the store does not have:")
        for o in state.orphans:
            print(f"  {o['type']} {o['id']} ({o['eid']})")


def cmd_report(args) -> int:
    store, _ = open_store(args)
    if not args.no_pull:
        store.pull()
    state = store.replay()
    if args.json:
        print(json.dumps(encode({
            "project": store.project, "nodes": len(state.nodes), "conflicts": state.conflicts,
            "aliases": state.aliases, "orphans": state.orphans,
        }), indent=2, ensure_ascii=False))
        return 0
    live = len(store._read_live())
    total = len(store.events())
    print(f"{store.project}: {len(state.nodes)} nodes from {total} events ({total - live} archived)")
    _print_findings(state)
    if not (state.conflicts or state.aliases or state.orphans):
        print("No concurrent edits, aliases or orphaned events.")
    return 0


def cmd_record(args) -> int:
    """Turn edits made to the view file directly into events."""
    store, cfg = open_store(args)
    target = view_path(args, cfg)
    if target is None or not target.is_file():
        raise StoreError(f"no view at {target}")
    text = target.read_text(encoding="utf-8")
    edited = yaml.safe_load(text)
    base_commit = view_commit(text)
    with store.lock():
        store.pull()
        # Diff against the store as the view was generated from, so changes pushed since
        # are not reverted; replay then applies ours over theirs, per field.
        base = store.replay_at(base_commit).to_dag() if base_commit else store.replay().to_dag()
        bodies = diff_events(base, edited)
        if not bodies:
            print(f"No edits in {target} to record.")
            return 0
        written = store.write_events(bodies)
        store.commit_and_push(f"record {len(written)} edit(s) from the view",
                              on_rebase=lambda: store.resolve_collisions(written))
        state = store.replay()
        store.write_view(target, state)
    print(f"Recorded {len(written)} event(s) from {target}.")
    _print_findings(state)
    return 0


def cmd_prune(args) -> int:
    store, _ = open_store(args)
    statuses = args.statuses.split(",") if args.statuses else DEFAULT_CLOSED
    with store.lock():
        store.pull()
        state = store.replay()
        closed = store.closed_nodes(state, args.days, statuses)
        if not closed:
            print(f"Nothing {'/'.join(statuses)} older than {args.days:g} day(s) to archive.")
            return 0
        if args.dry_run:
            print(f"Would archive the events of {len(closed)} node(s): {', '.join(closed)}")
            return 0
        r = store.archive(closed, state)
        if not r:
            print("Their events are already archived.")
            return 0
        store.commit_and_push(f"prune {store.project}: archive {r['nodes']} closed node(s) to {r['file']}")
    print(f"Archived {r['events']} event(s) of {r['nodes']} closed node(s) to {r['file']}. "
          f"Replay still reads them, so the DAG is unchanged.")
    return 0


def cmd_verify(args) -> int:
    store, _ = open_store(args)
    if not args.no_pull:
        store.pull()
    other = yaml.safe_load(Path(args.against).read_text(encoding="utf-8"))
    problems = compare(store.replay().to_dag(), other)
    if problems:
        print(f"Replay of {store.project} differs from {args.against}:")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"Replay of {store.project} reproduces {args.against} ({len(iter_nodes(other))} nodes).")
    return 0


def cmd_sync(args) -> int:
    store, _ = open_store(args)
    with store.lock():
        store.pull()
        pushed = store.commit_and_push("sync")
    print("Synced." if pushed else "Not pushed.")
    return 0 if pushed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The shared, event-sourced store for the hypothesis DAG.")
    parser.add_argument("--store", help="Clone path or URL of the store (overrides dag_store in research.yaml)")
    parser.add_argument("--project", help="Project folder in the store (overrides dag_project)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Clone the store if needed and create the project folder")
    p = sub.add_parser("import", help="Seed an empty project from an existing hypothesis-dag.yaml")
    p.add_argument("--from", dest="source", help="The YAML to import (default: dag_path)")
    p = sub.add_parser("view", help="Pull and regenerate the YAML view")
    p.add_argument("--view", help="Where to write it (default: dag_path)")
    p = sub.add_parser("report", help="Concurrent edits, aliases and orphaned events")
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-pull", action="store_true", help="Report on the local clone as it is")
    p = sub.add_parser("record", help="Record edits made directly to the view file as events")
    p.add_argument("--view", help="The edited view (default: dag_path)")
    p = sub.add_parser("prune", help="Archive the events of closed nodes; replay still reads them")
    p.add_argument("--days", type=float, default=90, help="Only nodes untouched this long (default 90)")
    p.add_argument("--statuses", help=f"Comma-separated closed statuses (default {','.join(DEFAULT_CLOSED)})")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("verify", help="Check replay reproduces a YAML file's content")
    p.add_argument("--against", required=True)
    p.add_argument("--no-pull", action="store_true")
    sub.add_parser("sync", help="Push anything left unpushed")

    args = parser.parse_args(argv)
    handler = {"init": cmd_init, "import": cmd_import, "view": cmd_view, "report": cmd_report,
               "record": cmd_record, "prune": cmd_prune, "verify": cmd_verify, "sync": cmd_sync}[args.command]
    try:
        return handler(args)
    except (StoreError, TimeoutError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
