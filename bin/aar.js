#!/usr/bin/env node
// SPDX-FileCopyrightText: 2026 Dermot O'Brien
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// `aar` launcher — a zero-dependency thin wrapper.
//
// AAR's tooling is Python, but its INSTALL flow is the shared Node engine that
// ships with AAW (which AAR depends on). This launcher locates the sibling AAW
// bundle and delegates: `aaw install --framework <this AAR repo>`. No npm
// install, no node_modules, no bundling needed here.
//
//   aar install [--no-python]   Wire AAR shims, seed research.yaml + research/,
//                               pip-install requirements (needs AAW present).

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const HELP = `aar — AI-Assisted Research (RMS) installer

Usage:
  aar install [--no-python]   Install AAR into this workspace
  aar --help                  Show this help

AAR depends on AAW: the .ai-assisted-work submodule must be present (it provides
the shared install engine). Tooling runs in Python (pip).
`;

function findWorkspaceRoot(start) {
  let dir = path.resolve(start);
  for (;;) {
    if (existsSync(path.join(dir, ".git")) || existsSync(path.join(dir, ".aaw-config.yaml"))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) return path.resolve(start);
    dir = parent;
  }
}

/** Locate the AAW install engine across: npm dependency, hoisted node_modules, then submodule. */
function resolveAawBin(workspaceRoot) {
  // 1. AAW installed as an npm dependency (resolvable from this launcher).
  try {
    const pkg = createRequire(import.meta.url).resolve("ai-assisted-work/package.json");
    const bin = path.join(path.dirname(pkg), "bin", "aaw.js");
    if (existsSync(bin)) return bin;
  } catch {
    /* not an npm dep — try other layouts */
  }
  // 2. Hoisted into the workspace's node_modules.
  const hoisted = path.join(workspaceRoot, "node_modules", "ai-assisted-work", "bin", "aaw.js");
  if (existsSync(hoisted)) return hoisted;
  // 3. Sibling git submodule (back-compat).
  const submodule = path.join(workspaceRoot, ".ai-assisted-work", "bin", "aaw.js");
  if (existsSync(submodule)) return submodule;
  return undefined;
}

function main(argv) {
  const command = argv[0];
  if (command === "--help" || command === "-h" || command === "help") {
    process.stdout.write(HELP);
    return 0;
  }
  if (command !== undefined && command !== "install") {
    process.stderr.write(`Unknown command: ${command}\n\n${HELP}`);
    return 2;
  }

  const frameworkRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  const workspaceRoot = findWorkspaceRoot(process.cwd());
  const aawBin = resolveAawBin(workspaceRoot);
  if (!aawBin) {
    process.stderr.write(
      "AAR requires AAW (it provides the shared install engine). Install it as an\n" +
        "npm dependency (npm i github:dermot-obrien/ai-assisted-work) or add the\n" +
        ".ai-assisted-work submodule, then re-run `aar install`.\n",
    );
    return 1;
  }

  const passthrough = command === "install" ? argv.slice(1) : [];
  const result = spawnSync(
    "node",
    [aawBin, "install", "--framework", frameworkRoot, ...passthrough],
    { stdio: "inherit" },
  );
  return result.status ?? 1;
}

process.exit(main(process.argv.slice(2)));
