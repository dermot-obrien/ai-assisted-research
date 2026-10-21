#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""Moved to the research-dag skill: run <skills>/research-dag/bin/dag_store.py.

This launcher keeps the old path working for one release (research 4.x). It runs the
research-dag skill's copy, installed beside this skill, with the same arguments.
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(os.path.dirname(os.path.dirname(HERE)), "research-dag", "bin", "dag_store.py")
if not os.path.isfile(TARGET):
    print("dag_store.py moved to the research-dag skill, which is not installed beside research. "
          "Install it: node <aaw>/bin/skills.mjs install research-dag --bundle <ai-assisted-research>",
          file=sys.stderr)
    sys.exit(2)
print("note: research/bin/dag_store.py moved to research-dag/bin/dag_store.py; this path goes in research 5.0.0.",
      file=sys.stderr)
sys.path.insert(0, os.path.dirname(TARGET))
sys.argv[0] = TARGET
runpy.run_path(TARGET, run_name="__main__")
