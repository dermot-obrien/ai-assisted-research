#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""Post-install check for an AI-Assisted Research skill (DD-11 of AI-Assisted Work).

Run from the workspace root, with SKILL_DIR set to the installed skill's directory:

    python bin/check.py

Checks what the skill needs locally: Python 3.10 or newer, the Python packages its tools
import, and, for every skill that reads it, research.yaml ($RMS_ROOT, or the working
directory and its parents) with the paths it names. A path the workspace has not created
yet, such as the DAG before the first hypothesis, is a warning; a path whose folder does
not exist is a problem.

Exit 0: correct (warnings may be printed). Exit 1: problems, one line each.
Exit 2: usage or environment error. Offline and read-only.

The same file ships in every skill of this bundle, so each is complete on its own; CI
checks the copies are identical. What differs by skill is in NEEDS below.
"""
import importlib.util
import os
import sys

if sys.version_info < (3, 10):
    print(f"Python {sys.version.split()[0]} is too old: the research tools need 3.10 or newer.",
          file=sys.stderr)
    sys.exit(2)
if len(sys.argv) > 1:
    print("usage: check.py   (run from the workspace root; takes no arguments)", file=sys.stderr)
    sys.exit(2)

SKILL_DIR = os.path.abspath(os.environ.get("SKILL_DIR")
                            or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL = os.path.basename(SKILL_DIR)

# The packages each skill's own tools import, as pip names them, and whether it reads
# research.yaml. A skill not listed reads research.yaml and imports nothing.
NEEDS = {
    "research-dag": {"packages": {"yaml": "PyYAML"}},
    "aar-housekeep": {"packages": {"yaml": "PyYAML"}},
    "aar-reconcile": {"packages": {"yaml": "PyYAML"}},
    "aar-run-audit": {"packages": {"yaml": "PyYAML"}},
    "literature-discovery": {"packages": {"yaml": "PyYAML", "requests": "requests"}, "research_yaml": False},
}
need = NEEDS.get(SKILL, {})
problems, warnings = [], []

for module, package in need.get("packages", {}).items():
    if importlib.util.find_spec(module) is None:
        problems.append(f"{package} is not installed for this Python. Run: python -m pip install {package}")


def read_config(path):
    """research.yaml as a dict: with PyYAML where installed, else its top-level scalars."""
    text = open(path, encoding="utf-8").read()
    if importlib.util.find_spec("yaml") is not None:
        import yaml
        return yaml.safe_load(text) or {}
    out = {}
    for line in text.splitlines():
        if line[:1] in (" ", "\t", "#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.split(" #")[0].strip().strip("'\"")
        if value:
            out[key.strip()] = value
    return out


def find_root():
    env = os.environ.get("RMS_ROOT")
    if env:
        return os.path.abspath(os.path.expanduser(env)), "RMS_ROOT"
    d = os.getcwd()
    while True:
        if os.path.isfile(os.path.join(d, "research.yaml")):
            return d, None
        up = os.path.dirname(d)
        if up == d:
            return None, None
        d = up


if need.get("research_yaml", True):
    root, via = find_root()
    config = os.path.join(root, "research.yaml") if root else None
    shown = config
    if config and not os.path.relpath(config, os.getcwd()).startswith(".."):
        shown = os.path.relpath(config, os.getcwd())
    if not root or not os.path.isfile(config):
        where = f"RMS_ROOT={os.environ.get('RMS_ROOT')}" if via else f"{os.getcwd()} or above"
        problems.append(f"research.yaml: not found in {where}. Run the AI-Assisted Research installer in "
                        f"the workspace root, or copy research-dag's assets/research.yaml.example there.")
    else:
        try:
            cfg = read_config(config)
        except Exception as e:  # noqa: BLE001 - any parse failure is the same problem
            cfg = None
            problems.append(f"{shown}: could not be read ({e}). Fix the YAML.")
        if cfg is not None and not isinstance(cfg, dict):
            problems.append(f"{shown}: is not a mapping of keys to paths. Start from assets/research.yaml.example.")
        elif cfg is not None:
            later = {
                "dag_path": "the first hypothesis creates it",
                "node_index_path": "generate_node_index.py writes it",
                "work_items_path": "starting a research work item creates it",
            }
            for key, when in later.items():
                value = cfg.get(key)
                if not isinstance(value, str) or not value.strip():
                    problems.append(f"{shown}: {key} is not set. Add it, as a path relative to research.yaml.")
                    continue
                p = os.path.normpath(os.path.join(root, value))
                folder = p if key == "work_items_path" else os.path.dirname(p)
                if os.path.exists(p):
                    continue
                if key != "work_items_path" and not os.path.isdir(folder):
                    problems.append(f"{shown}: {key} {value} is in {folder}, which does not exist. "
                                    f"Create the folder, or correct {key}.")
                else:
                    warnings.append(f"{shown}: {key} {value} does not exist yet; {when}.")

for w in warnings:
    print(f"warning: {w}")
for p in problems:
    print(p)
if not problems:
    print(f"{SKILL}: ok")
sys.exit(1 if problems else 0)
