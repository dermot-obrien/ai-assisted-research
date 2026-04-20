#!/usr/bin/env python3
# Copyright 2026 Dermot O'Brien -- GPLv3
"""
Load research.yaml from the consumer repo and expose resolved paths.

Consumer repos declare paths in a research.yaml at their root (the workspace
signpost). Tools in this directory read that config rather than hardcoding
project-specific paths, so they are reusable across projects.

Expected research.yaml schema (excerpt):

    dag_path: "research/hypothesis-dag.yaml"
    node_index_path: "research/node-index.yaml"
    work_items_path: ".irregular-timeseries-intent/change/work-items/"
    dashboard:
      title: "Project Research Hypothesis Dashboard"
      experiments_dir: "autoresearch/experiments"
      breakthroughs: "autoresearch/breakthroughs.yaml"
      output_html: "autoresearch/dashboard.html"
      output_mermaid: "RESEARCH_DASHBOARD.md"

All string path values are resolved relative to the directory containing
research.yaml. Project-specific keys (e.g. a trading dashboard) can be
declared in research.yaml too and read via the generic `cfg.path(dotted)`
accessor — this helper only names the shared DAG-framework paths.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` (or this file) to find the nearest research.yaml."""
    start = (start or Path(__file__)).resolve()
    for parent in [start, *start.parents]:
        if (parent / "research.yaml").is_file():
            return parent
    raise FileNotFoundError(
        "research.yaml not found in any ancestor directory of "
        f"{start}. Create one at the repo root — see rms_config.py docstring."
    )


class Config:
    def __init__(self, repo_root: Path | None = None):
        self.repo_root = repo_root or find_repo_root()
        self._raw = yaml.safe_load(
            (self.repo_root / "research.yaml").read_text(encoding="utf-8")
        )

    def _get(self, dotted: str, default: Any = ...) -> Any:
        node: Any = self._raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                if default is ...:
                    raise KeyError(f"research.yaml missing key: {dotted}")
                return default
            node = node[part]
        return node

    def path(self, dotted: str, default: str | None = None) -> Path:
        value = self._get(dotted, default if default is not None else ...)
        return self.repo_root / value

    # --- Core DAG framework paths ---
    @property
    def dag_path(self) -> Path:
        return self.path("dag_path")

    @property
    def node_index_path(self) -> Path:
        return self.path("node_index_path")

    @property
    def work_items_path(self) -> Path:
        return self.path("work_items_path")

    # --- Dashboard paths ---
    @property
    def dashboard_title(self) -> str:
        return self._get("dashboard.title", "Research Hypothesis Dashboard")

    @property
    def experiments_dir(self) -> Path:
        return self.path("dashboard.experiments_dir")

    @property
    def breakthroughs_path(self) -> Path:
        return self.path("dashboard.breakthroughs")

    @property
    def dashboard_html(self) -> Path:
        return self.path("dashboard.output_html")

    @property
    def dashboard_mermaid(self) -> Path:
        return self.path("dashboard.output_mermaid")

    @property
    def papers_path(self) -> Path:
        return self.path("dashboard.papers")

    @property
    def findings_edges_path(self) -> Path:
        return self.path("dashboard.findings_edges")


def load() -> Config:
    return Config()
