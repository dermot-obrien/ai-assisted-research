#!/usr/bin/env python3
# Copyright 2026 Dermot O'Brien -- GPLv3
"""
Generate an interactive hypothesis research dashboard.

Reads the hypothesis DAG, experiment log, and node index to produce
a self-contained HTML file with:
- Interactive D3.js force-directed graph of the hypothesis tree
- Color-coded nodes by status (validated, pending, in_progress, etc.)
- Click-to-expand node details (hypothesis, evidence, findings)
- Experiment timeline
- Summary statistics
- "Ready" nodes highlighted as the research frontier

Usage:
    python .ai-assisted-research/tools/generate_dashboard.py

Paths are resolved via research.yaml at the consumer repo root.
"""

from __future__ import annotations

import json
from datetime import datetime

import yaml

import rms_config

_cfg = rms_config.load()


def load_dag():
    """Load hypothesis DAG nodes."""
    with open(_cfg.dag_path, encoding="utf-8") as f:
        dag = yaml.safe_load(f)

    nodes = []
    for key in dag:
        val = dag[key]
        if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict) and "id" in val[0]:
            nodes = val
            break
    return nodes


def load_node_index():
    """Load the precomputed node index."""
    if not _cfg.node_index_path.exists():
        return {}
    with open(_cfg.node_index_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_papers():
    """Load publication tracking data from the configured file.

    Normalises each paper so the list-valued fields the dashboard renders
    (`nodes`, `breakthroughs`) are always present as lists. A paper missing
    one of these would otherwise make the embedded JS throw on `.join()` /
    `.includes()`, and because the whole dashboard is a single inline script,
    that one bad record blanks the ENTIRE graph (not just the papers panel).
    """
    path = _cfg.papers_path
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    papers = data.get("papers", []) or []
    for p in papers:
        for field in ("nodes", "breakthroughs"):
            if not isinstance(p.get(field), list):
                p[field] = []
    return papers


def load_findings_edges():
    """Load cross-node findings relationships from the configured file."""
    path = _cfg.findings_edges_path
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("findings_edges", [])


def load_experiments():
    """Load all experiment logs from the experiments directory."""
    if not _cfg.experiments_dir.exists():
        return []
    exps = []
    for log_file in sorted(_cfg.experiments_dir.glob("*experiment-log.jsonl")):
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    exp = json.loads(line)
                    exp["_source"] = log_file.name
                    exps.append(exp)
    # Sort by timestamp if available, then by experiment id
    exps.sort(key=lambda e: (e.get("timestamp", ""), e.get("experiment_id", e.get("id", 0))))
    return exps


def load_breakthroughs_from_experiments(experiments):
    """Auto-extract breakthroughs from experiment log (is_breakthrough=true)."""
    auto_bts = []
    for e in experiments:
        if e.get("is_breakthrough"):
            auto_bts.append({
                "id": f"B-exp{e['experiment_id']}",
                "experiment": e["experiment_id"],
                "node": e.get("node_id", ""),
                "title": e.get("breakthrough_title", e.get("hypothesis", "")[:50]),
                "description": e.get("notes", e.get("hypothesis", ""))[:200],
                "impact": e.get("breakthrough_impact", ""),
                "date": e.get("timestamp", "")[:10],
            })
    return auto_bts


def load_breakthroughs():
    """Load breakthroughs from breakthroughs.yaml (single source of truth).

    Normalises field names: breakthroughs.yaml uses both 'experiment'/'node'
    (B1-B6) and 'experiment_id'/'node_id' (B7+). This function normalises to
    'experiment' and 'node' for consistency.
    """
    if not _cfg.breakthroughs_path.exists():
        return []
    with open(_cfg.breakthroughs_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    bts = []
    for b in data.get("breakthroughs", []):
        bts.append({
            "id": b.get("id", ""),
            "experiment": b.get("experiment", b.get("experiment_id", 0)),
            "node": b.get("node", b.get("node_id", "")),
            "title": b.get("title", ""),
            "description": b.get("description", "")[:200],
            "impact": b.get("impact", ""),
            "date": b.get("date", ""),
        })
    return bts


def generate_html(nodes, node_index, experiments, breakthroughs, papers, findings_edges):
    """Generate the self-contained HTML dashboard."""

    # Prepare node data for D3
    d3_nodes = []
    d3_links = []
    status_colors = {
        "validated": "#22c55e",
        "completed": "#3b82f6",
        "in_progress": "#f59e0b",
        "partially_tested": "#f97316",
        "pending": "#94a3b8",
        "ineffective": "#ef4444",
        "framed": "#a855f7",
        "contested": "#fb923c",
    }

    # Build node lookup
    node_map = {}
    for n in nodes:
        nid = n.get("id", "?")
        node_map[nid] = n
        d3_nodes.append({
            "id": nid,
            "parent": n.get("parent"),
            "status": n.get("status", "pending"),
            "hypothesis": n.get("hypothesis", ""),
            "work_item": n.get("work_item_id", ""),
            "actual_performance": n.get("actual_performance", ""),
            "evidence": n.get("evidence", ""),
            "notes": n.get("notes", ""),
            "color": status_colors.get(n.get("status", "pending"), "#94a3b8"),
            "contested": n.get("status") == "contested",
            "audit_findings": n.get("audit_findings", []),
        })
        if n.get("parent"):
            d3_links.append({
                "source": n["parent"],
                "target": nid,
            })

    # Get ready nodes from index
    ready_ids = [n["id"] for n in node_index.get("ready", [])]

    # Golden path nodes: ready nodes with golden_path flag
    golden_path_ids = [n["id"] for n in node_index.get("ready", []) if n.get("golden_path")]

    # Statistics
    from collections import Counter
    status_counts = Counter(n.get("status", "unknown") for n in nodes)

    # Experiment data for timeline — supports both ML and strategy log formats
    exp_data = []
    for e in experiments:
        ratio = e.get("val_mse_ratio") or e.get("test_mse_ratio") or e.get("fitness")
        source = e.get("_source", "experiment-log.jsonl")
        is_strategy = "strategy" in source
        exp_data.append({
            "id": e.get("experiment_id", e.get("id", 0)),
            "hypothesis": e.get("hypothesis", ""),
            "ratio": ratio,
            "improved": e.get("improved", e.get("breakthrough", False)),
            "success": e.get("success", not e.get("contested", False)),
            "timestamp": e.get("timestamp", ""),
            "source": "strategy" if is_strategy else "ml",
        })

    # Breakthrough data — merge manual list with auto-extracted from experiments
    auto_bts = load_breakthroughs_from_experiments(experiments)
    manual_exp_ids = {b["experiment"] for b in breakthroughs}
    # Add auto breakthroughs that aren't in the manual list
    all_breakthroughs = list(breakthroughs)
    for ab in auto_bts:
        if ab["experiment"] not in manual_exp_ids:
            all_breakthroughs.append(ab)
    all_breakthroughs.sort(key=lambda b: b["experiment"])
    breakthrough_node_ids = list(set(b["node"] for b in all_breakthroughs if b.get("node")))
    breakthroughs_json = json.dumps(all_breakthroughs, indent=2)
    breakthrough_nodes_json = json.dumps(breakthrough_node_ids)
    golden_path_json = json.dumps(golden_path_ids)

    # Paper and findings data
    papers_json = json.dumps(papers, indent=2)
    paper_node_ids = list(set(nid for p in papers for nid in p["nodes"]))
    paper_nodes_json = json.dumps(paper_node_ids)
    findings_edges_json = json.dumps(findings_edges, indent=2)

    nodes_json = json.dumps(d3_nodes, indent=2)
    links_json = json.dumps(d3_links, indent=2)
    ready_json = json.dumps(ready_ids)
    experiments_json = json.dumps(exp_data, indent=2)
    status_counts_json = json.dumps(dict(status_counts))
    n_breakthroughs = len(breakthroughs)
    dashboard_title = _cfg.dashboard_title

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{dashboard_title}</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; }}
.header {{ background: #1e293b; padding: 16px 24px; border-bottom: 1px solid #334155; display: flex; justify-content: space-between; align-items: center; }}
.header h1 {{ font-size: 20px; font-weight: 600; }}
.header .stats {{ display: flex; gap: 16px; font-size: 13px; }}
.stat {{ padding: 4px 12px; border-radius: 12px; font-weight: 500; }}
.main {{ display: grid; grid-template-columns: 1fr 380px; height: calc(100vh - 56px); }}
.graph-container {{ position: relative; overflow: hidden; }}
svg {{ width: 100%; height: 100%; }}
.sidebar {{ background: #1e293b; border-left: 1px solid #334155; overflow-y: auto; padding: 16px; }}
.sidebar h2 {{ font-size: 16px; margin-bottom: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; font-size: 11px; }}
.node-detail {{ background: #0f172a; border-radius: 8px; padding: 16px; margin-bottom: 12px; border: 1px solid #334155; }}
.node-detail h3 {{ font-size: 14px; margin-bottom: 8px; }}
.node-detail .status-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
.node-detail p {{ font-size: 12px; color: #94a3b8; margin-top: 6px; line-height: 1.5; }}
.node-detail .perf {{ color: #22c55e; font-weight: 500; font-size: 12px; margin-top: 6px; }}
.ready-list {{ list-style: none; }}
.ready-list li {{ padding: 8px 12px; margin-bottom: 4px; background: #1a2744; border-radius: 6px; border-left: 3px solid #f59e0b; font-size: 12px; cursor: pointer; }}
.ready-list li:hover {{ background: #1e3a5f; }}
.ready-list li .rid {{ font-weight: 600; color: #f59e0b; }}
.experiment-timeline {{ margin-top: 16px; }}
.exp-row {{ display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 11px; border-bottom: 1px solid #1e293b; }}
.exp-row .eid {{ width: 24px; text-align: right; color: #64748b; }}
.exp-row .bar {{ height: 6px; border-radius: 3px; min-width: 2px; }}
.exp-row .label {{ flex: 1; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }}
.legend-item {{ display: flex; align-items: center; gap: 4px; font-size: 11px; }}
.legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
.node circle {{ stroke-width: 2px; cursor: pointer; transition: r 0.2s; }}
.node circle:hover {{ stroke: #fff; }}
.node text {{ font-size: 9px; fill: #94a3b8; pointer-events: none; }}
.link {{ stroke: #334155; stroke-width: 1.5px; fill: none; }}
.node.ready circle {{ stroke: #f59e0b; stroke-width: 3px; stroke-dasharray: 4,2; animation: pulse 2s infinite; }}
.node.golden circle {{ stroke: #fbbf24; stroke-width: 4px; animation: goldpulse 1.5s infinite; }}
@keyframes goldpulse {{ 0%,100% {{ filter: drop-shadow(0 0 4px #fbbf24); }} 50% {{ filter: drop-shadow(0 0 12px #fbbf24); }} }}
@keyframes pulse {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
.tab-bar {{ display: flex; gap: 0; margin-bottom: 12px; }}
.tab {{ padding: 6px 12px; font-size: 12px; cursor: pointer; border: 1px solid #334155; background: #0f172a; color: #94a3b8; }}
.tab:first-child {{ border-radius: 6px 0 0 6px; }}
.tab:last-child {{ border-radius: 0 6px 6px 0; }}
.tab.active {{ background: #334155; color: #e2e8f0; }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}
.search {{ width: 100%; padding: 8px 12px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; color: #e2e8f0; font-size: 12px; margin-bottom: 12px; }}
.search::placeholder {{ color: #475569; }}
.breakthrough-card {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border: 1px solid #fbbf24; border-radius: 8px; padding: 14px; margin-bottom: 10px; cursor: pointer; }}
.breakthrough-card:hover {{ border-color: #fde68a; }}
.breakthrough-card .bt-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
.breakthrough-card .bt-star {{ color: #fbbf24; font-size: 16px; }}
.breakthrough-card .bt-title {{ font-size: 13px; font-weight: 600; color: #fde68a; }}
.breakthrough-card .bt-exp {{ font-size: 10px; color: #64748b; }}
.breakthrough-card .bt-desc {{ font-size: 11px; color: #94a3b8; line-height: 1.5; margin-bottom: 6px; }}
.breakthrough-card .bt-impact {{ font-size: 11px; color: #22c55e; font-style: italic; }}
.node.breakthrough polygon:hover {{ stroke: #fff; stroke-width: 4px; }}
.node polygon {{ cursor: pointer; transition: stroke 0.2s; }}
</style>
</head>
<body>
<div class="header">
  <h1>{dashboard_title}</h1>
  <div class="stats">
    <span class="stat" style="background:#22c55e33;color:#22c55e" id="stat-validated">0 validated</span>
    <span class="stat" style="background:#3b82f633;color:#3b82f6" id="stat-completed">0 completed</span>
    <span class="stat" style="background:#f59e0b33;color:#f59e0b" id="stat-active">0 active</span>
    <span class="stat" style="background:#94a3b833;color:#94a3b8" id="stat-pending">0 pending</span>
    <span class="stat" style="background:#ef444433;color:#ef4444" id="stat-ineffective">0 ineffective</span>
    <span class="stat" style="background:#6366f133;color:#6366f1">{len(exp_data)} experiments</span>
    <span class="stat" style="background:#fbbf2433;color:#fbbf24">{n_breakthroughs} breakthroughs</span>
  </div>
</div>
<div class="main">
  <div class="graph-container" id="graph"></div>
  <div class="sidebar">
    <div class="tab-bar">
      <div class="tab active" data-tab="selected">Selected</div>
      <div class="tab" data-tab="breakthroughs">Breakthroughs</div>
      <div class="tab" data-tab="ready">Ready ({len(ready_ids)})</div>
      <div class="tab" data-tab="papers">Papers</div>
      <div class="tab" data-tab="experiments">Experiments</div>
    </div>

    <div class="tab-content active" id="tab-selected">
      <div id="node-info">
        <div class="node-detail">
          <h3>Click a node to see details</h3>
          <p>The graph shows the full hypothesis search space. Green = validated, blue = completed, orange = in progress, gray = pending, red = ineffective.</p>
          <p style="margin-top:12px">Pulsing amber borders = ready to start (parents resolved).</p>
        </div>
      </div>
      <h2 style="margin-top:16px">Legend</h2>
      <div class="legend">
        <div class="legend-item"><div class="legend-dot" style="background:#22c55e"></div> Validated</div>
        <div class="legend-item"><div class="legend-dot" style="background:#3b82f6"></div> Completed</div>
        <div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div> In Progress</div>
        <div class="legend-item"><div class="legend-dot" style="background:#f97316"></div> Partially Tested</div>
        <div class="legend-item"><div class="legend-dot" style="background:#94a3b8"></div> Pending</div>
        <div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div> Ineffective</div>
      </div>
      <h2 style="margin-top:12px">Path Indicators</h2>
      <div class="legend">
        <div class="legend-item"><div style="width:14px;height:14px;background:#fbbf24;transform:rotate(45deg);border-radius:2px"></div> Breakthrough</div>
        <div class="legend-item"><div class="legend-dot" style="background:#ef4444;position:relative"><span style="position:absolute;top:-3px;left:1px;font-size:8px;color:#fff;font-weight:bold">&#10007;</span></div> Dead end</div>
        <div class="legend-item"><div style="width:20px;height:3px;background:#22c55e;border-radius:2px"></div> Promising path</div>
        <div class="legend-item"><div style="width:20px;height:2px;background:#f59e0b;border-radius:2px"></div> Active path</div>
        <div class="legend-item"><div style="width:20px;height:1px;background:#ef4444;opacity:0.4;border-radius:2px"></div> Cold path</div>
        <div class="legend-item"><span style="font-size:10px">&#128196;</span> Paper contribution</div>
      </div>
    </div>

    <div class="tab-content" id="tab-breakthroughs">
      <h2>Key Breakthroughs</h2>
      <p style="font-size:12px;color:#64748b;margin-bottom:12px">Milestones that changed the direction of research. Marked with a star on the graph.</p>
      <div id="breakthrough-list"></div>
    </div>

    <div class="tab-content" id="tab-ready">
      <h2>Research Frontier</h2>
      <p style="font-size:12px;color:#64748b;margin-bottom:12px">Nodes whose parents are all resolved. Ready to start.</p>
      <ul class="ready-list" id="ready-list"></ul>
    </div>

    <div class="tab-content" id="tab-papers">
      <h2>Publications</h2>
      <div id="papers-list"></div>
      <h2 style="margin-top:16px">Findings Graph</h2>
      <p style="font-size:11px;color:#64748b;margin-bottom:8px">How findings relate across the DAG</p>
      <div id="findings-list"></div>
    </div>

    <div class="tab-content" id="tab-experiments">
      <h2>Experiment Timeline</h2>
      <div class="experiment-timeline" id="exp-timeline"></div>
    </div>
  </div>
</div>

<script>
const nodes = {nodes_json};
const links = {links_json};
const readyIds = new Set({ready_json});
const experiments = {experiments_json};
const statusCounts = {status_counts_json};
const breakthroughs = {breakthroughs_json};
const breakthroughNodeIds = new Set({breakthrough_nodes_json});
const goldenPathIds = new Set({golden_path_json});
const papers = {papers_json};
const paperNodeIds = new Set({paper_nodes_json});
const findingsEdges = {findings_edges_json};

// Update header stats
document.getElementById('stat-validated').textContent = (statusCounts['validated']||0) + ' validated';
document.getElementById('stat-completed').textContent = (statusCounts['completed']||0) + ' completed';
document.getElementById('stat-active').textContent = ((statusCounts['in_progress']||0)+(statusCounts['partially_tested']||0)) + ' active';
document.getElementById('stat-pending').textContent = (statusCounts['pending']||0) + ' pending';
document.getElementById('stat-ineffective').textContent = (statusCounts['ineffective']||0) + ' ineffective';

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {{
  tab.addEventListener('click', () => {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
  }});
}});

// Ready list — golden path items first, then others
const readyList = document.getElementById('ready-list');
const readyNodes = nodes.filter(n => readyIds.has(n.id));
// Sort: golden path first
readyNodes.sort((a, b) => {{
  const aGold = goldenPathIds.has(a.id) ? 0 : 1;
  const bGold = goldenPathIds.has(b.id) ? 0 : 1;
  return aGold - bGold;
}});
readyNodes.forEach(n => {{
  const li = document.createElement('li');
  const isGold = goldenPathIds.has(n.id);
  if (isGold) {{
    li.style.borderLeft = '3px solid #fbbf24';
    li.style.background = '#1a1a2e';
  }}
  const badge = isGold ? '<span style="background:#fbbf2433;color:#fbbf24;padding:1px 6px;border-radius:3px;font-size:9px;font-weight:700;margin-left:4px">GOLDEN PATH</span>' : '';
  li.innerHTML = '<span class="rid">' + n.id + '</span>' + badge + ' ' + n.hypothesis.substring(0,70) + (n.hypothesis.length > 70 ? '...' : '');
  li.addEventListener('click', () => showNodeDetail(n));
  readyList.appendChild(li);
}});

// Experiment timeline
const expTimeline = document.getElementById('exp-timeline');
const maxRatio = Math.max(...experiments.filter(e => e.ratio && e.ratio < 10).map(e => e.ratio), 2);
experiments.forEach(e => {{
  const row = document.createElement('div');
  row.className = 'exp-row';
  const barWidth = e.ratio && e.ratio < 10 ? Math.max(2, (e.ratio / maxRatio) * 150) : 2;
  const barColor = e.improved ? '#22c55e' : (e.ratio && e.ratio < 1 ? '#3b82f6' : '#ef4444');
  const ratioStr = e.ratio ? e.ratio.toFixed(4) : 'N/A';
  row.innerHTML = '<span class="eid">#' + e.id + '</span>' +
    '<div class="bar" style="width:' + barWidth + 'px;background:' + barColor + '"></div>' +
    '<span style="width:55px;font-size:10px;color:' + (e.ratio && e.ratio < 1 ? '#22c55e' : '#94a3b8') + '">' + ratioStr + '</span>' +
    '<span class="label">' + e.hypothesis.substring(0,50) + '</span>';
  expTimeline.appendChild(row);
}});

// Node detail panel
function showNodeDetail(n) {{
  const info = document.getElementById('node-info');
  let html = '<div class="node-detail">';
  var contestedMarker = n.contested ? ' <span title="Contested: audit findings raised concerns about these results" style="color:#fb923c;font-size:16px;cursor:help">&#9888;</span>' : '';  // eslint-disable-line
  html += '<h3>' + n.id + contestedMarker + ' <span class="status-badge" style="background:' + n.color + '33;color:' + n.color + '">' + n.status + '</span></h3>';
  html += '<p style="color:#e2e8f0">' + n.hypothesis + '</p>';
  if (n.work_item) html += '<p>Work Item: <strong>' + n.work_item + '</strong></p>';
  if (n.actual_performance) html += '<div class="perf">' + n.actual_performance + '</div>';
  if (n.audit_findings && n.audit_findings.length > 0) {{
    html += '<div style="margin-top:8px;padding:8px;background:#451a0380;border:1px solid #fb923c;border-radius:6px">';
    html += '<div style="color:#fb923c;font-weight:600;font-size:11px;margin-bottom:4px">&#9888; AUDIT FINDINGS</div>';
    n.audit_findings.forEach(function(f) {{
      html += '<div style="font-size:11px;color:#fdba74;margin-bottom:4px">';
      html += '<strong>[' + (f.severity||'').toUpperCase() + ']</strong> ' + (f.finding||'');
      if (f.resolution) html += '<br/><span style="color:#86efac">Resolution: ' + f.resolution + '</span>';
      if (f.resolved_by_experiment) html += ' (Exp ' + f.resolved_by_experiment + ')';
      else html += ' <span style="color:#fca5a5">(UNRESOLVED)</span>';
      html += '</div>';
    }});
    html += '</div>';
  }}
  if (n.evidence) html += '<p style="margin-top:8px"><strong>Evidence:</strong> ' + n.evidence.substring(0,300) + (n.evidence.length > 300 ? '...' : '') + '</p>';
  if (n.notes) html += '<p style="margin-top:8px;color:#64748b"><em>' + n.notes.substring(0,200) + '</em></p>';
  if (readyIds.has(n.id)) html += '<p style="margin-top:8px;color:#f59e0b;font-weight:600">READY TO START</p>';
  // Show papers this node contributes to
  const nodePapers = papers.filter(p => (p.nodes || []).includes(n.id));
  if (nodePapers.length > 0) {{
    html += '<div style="margin-top:8px;padding:6px 10px;background:#f59e0b15;border-radius:6px;border:1px solid #f59e0b33">';
    html += '<p style="color:#f59e0b;font-size:11px;font-weight:600">&#128196; CONTRIBUTES TO PAPER</p>';
    nodePapers.forEach(p => {{
      const dot = p.status !== 'idea'
        ? '<span style="display:inline-block;width:6px;height:6px;background:#22c55e;border-radius:50%;margin-right:4px" title="Drafted"></span>'
        : '<span style="display:inline-block;width:6px;height:6px;background:#ef4444;border-radius:50%;margin-right:4px" title="Not drafted"></span>';
      const link = p.path ? ' <a href="' + p.path + '" target="_blank" style="color:#60a5fa;font-size:10px">[open]</a>' : '';
      html += '<p style="font-size:11px;color:#e2e8f0;margin-top:4px">' + dot + p.title + ' <span style="color:#64748b">(' + p.status + ')</span>' + link + '</p>';
    }});
    html += '</div>';
  }}

  // Show findings graph edges for this node
  const nodeFindings = findingsEdges.filter(e => e.from_node === n.id || e.to_node === n.id);
  if (nodeFindings.length > 0) {{
    html += '<div style="margin-top:8px">';
    html += '<p style="color:#94a3b8;font-size:11px;font-weight:600">FINDINGS CONNECTIONS</p>';
    nodeFindings.forEach(e => {{
      const other = e.from_node === n.id ? e.to_node : e.from_node;
      const dir = e.from_node === n.id ? '->' : '<-';
      html += '<p style="font-size:11px;margin-top:3px"><span style="color:' + (relationColors[e.relation]||'#94a3b8') + '">' + e.relation + '</span> ' + dir + ' ' + other + ': <span style="color:#64748b">' + e.note + '</span></p>';
    }});
    html += '</div>';
  }}

  // Show breakthroughs for this node
  const nodeBts = breakthroughs.filter(b => b.node === n.id);
  if (nodeBts.length > 0) {{
    html += '<div style="margin-top:10px;padding-top:10px;border-top:1px solid #334155">';
    html += '<p style="color:#fbbf24;font-weight:600;font-size:12px">&#9733; BREAKTHROUGHS</p>';
    nodeBts.forEach(b => {{
      html += '<div style="margin-top:6px;padding:8px;background:#1a1a2e;border-radius:6px;border-left:3px solid #fbbf24">';
      html += '<p style="color:#fde68a;font-size:12px;font-weight:600">' + b.title + ' <span style="color:#64748b;font-weight:normal">(Exp #' + b.experiment + ')</span></p>';
      html += '<p style="font-size:11px;color:#94a3b8;margin-top:4px">' + b.description + '</p>';
      html += '<p style="font-size:11px;color:#22c55e;margin-top:4px;font-style:italic">Impact: ' + b.impact + '</p>';
      html += '</div>';
    }});
    html += '</div>';
  }}
  html += '</div>';
  info.innerHTML = html;

  // Switch to selected tab
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelector('[data-tab="selected"]').classList.add('active');
  document.getElementById('tab-selected').classList.add('active');
}}

// Breakthrough list
const btList = document.getElementById('breakthrough-list');
breakthroughs.forEach(b => {{
  const card = document.createElement('div');
  card.className = 'breakthrough-card';
  card.innerHTML = '<div class="bt-header">' +
    '<span class="bt-star">&#9733;</span>' +
    '<span class="bt-title">' + b.title + '</span>' +
    '<span class="bt-exp">Exp #' + b.experiment + ' | ' + b.node + '</span>' +
    '</div>' +
    '<div class="bt-desc">' + b.description + '</div>' +
    '<div class="bt-impact">Impact: ' + b.impact + '</div>';
  card.addEventListener('click', () => {{
    const n = nodes.find(n => n.id === b.node);
    if (n) showNodeDetail(n);
  }});
  btList.appendChild(card);
}});

// Papers list
const papersList = document.getElementById('papers-list');
papers.forEach(p => {{
  const statusColors = {{ draft: '#f59e0b', submitted: '#3b82f6', accepted: '#22c55e', published: '#8b5cf6' }};
  const card = document.createElement('div');
  card.className = 'breakthrough-card';
  card.style.borderColor = statusColors[p.status] || '#334155';
  const drafted = p.status !== 'idea';
  const linkHtml = p.path ? '<a href="' + p.path + '" style="color:#60a5fa;text-decoration:underline;font-size:11px;display:block;margin-top:6px" target="_blank">Open draft &rarr;</a>' : '';
  const draftIndicator = drafted
    ? '<span style="display:inline-block;width:8px;height:8px;background:#22c55e;border-radius:50%;margin-right:6px" title="Draft exists"></span>'
    : '<span style="display:inline-block;width:8px;height:8px;background:#ef4444;border-radius:50%;margin-right:6px" title="Not yet drafted"></span>';
  card.innerHTML = '<div class="bt-header">' +
    draftIndicator +
    '<span class="bt-title" style="color:' + (statusColors[p.status]||'#e2e8f0') + '">' + p.title + '</span>' +
    '</div>' +
    '<div style="margin:4px 0"><span class="status-badge" style="background:' + (statusColors[p.status]||'#334155') + '33;color:' + (statusColors[p.status]||'#e2e8f0') + '">' + p.status.toUpperCase() + '</span>' +
    ' <span style="font-size:10px;color:#64748b">Target: ' + p.venue_target + '</span></div>' +
    '<div class="bt-desc">Key result: ' + p.key_result + '</div>' +
    '<div style="font-size:10px;color:#94a3b8;margin-top:4px">Nodes: ' + (p.nodes || []).join(', ') + '</div>' +
    '<div style="font-size:10px;color:#94a3b8">Breakthroughs: ' + (p.breakthroughs || []).join(', ') + '</div>' +
    linkHtml;
  papersList.appendChild(card);
}});

// Findings graph edges
const findingsList = document.getElementById('findings-list');
const relationColors = {{ contradicts: '#ef4444', reinforces: '#22c55e', unblocks: '#3b82f6', strengthens: '#22c55e', prompted: '#f59e0b', supersedes: '#a855f7' }};
findingsEdges.forEach(e => {{
  const row = document.createElement('div');
  row.style.cssText = 'padding:6px 8px;margin-bottom:4px;background:#0f172a;border-radius:4px;font-size:11px;border-left:3px solid ' + (relationColors[e.relation]||'#334155');
  row.innerHTML = '<span style="color:#e2e8f0;font-weight:600">' + e.from_node + '</span>' +
    ' <span style="color:' + (relationColors[e.relation]||'#94a3b8') + '">' + e.relation + '</span> ' +
    '<span style="color:#e2e8f0;font-weight:600">' + e.to_node + '</span>' +
    '<div style="color:#64748b;margin-top:2px">' + e.note + '</div>';
  findingsList.appendChild(row);
}});

// Compute path effectiveness: trace parent chains, classify as promising/ineffective/neutral
// A path is "promising" if it leads to validated nodes with actual_performance
// A path is "cold" if all children are ineffective
const nodeMap = new Map(nodes.map(n => [n.id, n]));
function getPathScore(nodeId) {{
  const n = nodeMap.get(nodeId);
  if (!n) return 0;
  if (n.status === 'validated') return 2;
  if (n.status === 'completed' || n.status === 'partially_tested') return 1;
  if (n.status === 'ineffective') return -1;
  return 0;
}}

// Classify links by path promise
function getLinkClass(link) {{
  const targetId = typeof link.target === 'string' ? link.target : link.target.id;
  const t = nodeMap.get(targetId);
  if (!t) return 'neutral';
  if (t.status === 'validated') return 'promising';
  if (t.status === 'ineffective') return 'cold';
  if (t.status === 'partially_tested' || t.status === 'in_progress') return 'active';
  return 'neutral';
}}

// D3 Force Graph
const container = document.getElementById('graph');
const width = container.clientWidth;
const height = container.clientHeight;

const svg = d3.select('#graph').append('svg')
  .attr('viewBox', [0, 0, width, height]);

const g = svg.append('g');

// Build hierarchy for layout
const nodeById = new Map(nodes.map(n => [n.id, n]));

const simulation = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(links).id(d => d.id).distance(60).strength(0.8))
  .force('charge', d3.forceManyBody().strength(-200))
  .force('center', d3.forceCenter(width / 2, height / 2))
  .force('collision', d3.forceCollide().radius(25))
  .force('y', d3.forceY(height / 2).strength(0.05));

const linkColors = {{ promising: '#22c55e', cold: '#ef4444', active: '#f59e0b', neutral: '#334155' }};

const link = g.append('g').selectAll('line')
  .data(links).join('line')
  .attr('class', 'link')
  .attr('stroke', d => linkColors[getLinkClass(d)] || '#334155')
  .attr('stroke-width', d => getLinkClass(d) === 'promising' ? 2.5 : (getLinkClass(d) === 'cold' ? 1 : 1.5))
  .attr('stroke-opacity', d => getLinkClass(d) === 'cold' ? 0.4 : 0.8);

let dragMoved = false;
const node = g.append('g').selectAll('g')
  .data(nodes).join('g')
  .attr('class', d => 'node' + (readyIds.has(d.id) ? ' ready' : '') + (breakthroughNodeIds.has(d.id) ? ' breakthrough' : '') + (goldenPathIds.has(d.id) ? ' golden' : ''))
  .on('click', (event, d) => {{ if (!dragMoved) showNodeDetail(d); }})
  .call(d3.drag()
    .on('start', (event, d) => {{ dragMoved = false; if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }})
    .on('drag', (event, d) => {{ dragMoved = true; d.fx = event.x; d.fy = event.y; }})
    .on('end', (event, d) => {{ if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }})
  );

// Breakthrough nodes get a diamond shape, others get circles
// Non-breakthrough nodes: circles
node.filter(d => !breakthroughNodeIds.has(d.id))
  .append('circle')
  .attr('r', d => {{
    if (d.id === 'H-000') return 16;
    if (d.status === 'validated') return 12;
    if (d.status === 'in_progress' || d.status === 'partially_tested') return 10;
    return 8;
  }})
  .attr('fill', d => d.color)
  .attr('stroke', d => d.contested ? '#fb923c' : readyIds.has(d.id) ? '#f59e0b' : d.color)
  .attr('stroke-width', d => d.contested ? 3 : 1.5)
  .attr('stroke-dasharray', d => d.contested ? '4,2' : 'none');

// Add warning icon on contested nodes
node.filter(d => d.contested)
  .append('text')
  .attr('text-anchor', 'middle')
  .attr('dy', -14)
  .attr('font-size', '14px')
  .text('\\u26A0')
  .style('fill', '#fb923c')
  .style('pointer-events', 'none');

// Breakthrough nodes: large diamond with gold glow
node.filter(d => breakthroughNodeIds.has(d.id))
  .append('polygon')
  .attr('points', d => {{
    const s = 18;
    return '0,' + (-s) + ' ' + s + ',0 0,' + s + ' ' + (-s) + ',0';
  }})
  .attr('fill', d => d.color)
  .attr('stroke', '#fbbf24')
  .attr('stroke-width', 3)
  .style('filter', 'drop-shadow(0 0 8px #fbbf24) drop-shadow(0 0 16px rgba(251,191,36,0.4))');

// Gold star inside breakthrough diamonds
node.filter(d => breakthroughNodeIds.has(d.id))
  .append('text')
  .attr('dy', 5)
  .attr('text-anchor', 'middle')
  .attr('font-size', '13px')
  .attr('fill', '#fbbf24')
  .attr('pointer-events', 'none')
  .text('\\u2605');

// Paper indicator: small document icon on nodes that contribute to papers
node.filter(d => paperNodeIds.has(d.id) && !breakthroughNodeIds.has(d.id))
  .append('text')
  .attr('dy', -2)
  .attr('dx', 14)
  .attr('font-size', '10px')
  .attr('fill', '#f59e0b')
  .attr('pointer-events', 'none')
  .text('\\uD83D\\uDCC4');

// Paper indicator on breakthrough diamonds too
node.filter(d => paperNodeIds.has(d.id) && breakthroughNodeIds.has(d.id))
  .append('text')
  .attr('dy', -16)
  .attr('dx', 14)
  .attr('font-size', '10px')
  .attr('fill', '#f59e0b')
  .attr('pointer-events', 'none')
  .text('\\uD83D\\uDCC4');

// Ineffective nodes: add X mark
node.filter(d => d.status === 'ineffective')
  .append('text')
  .attr('dy', 5)
  .attr('text-anchor', 'middle')
  .attr('font-size', '12px')
  .attr('fill', '#fff')
  .attr('pointer-events', 'none')
  .attr('font-weight', 'bold')
  .text('\\u2717');

node.append('text')
  .attr('dy', -18)
  .attr('text-anchor', 'middle')
  .attr('font-size', d => breakthroughNodeIds.has(d.id) ? '11px' : '9px')
  .attr('font-weight', d => breakthroughNodeIds.has(d.id) ? '700' : '400')
  .attr('fill', d => breakthroughNodeIds.has(d.id) ? '#fde68a' : '#94a3b8')
  .text(d => d.id);

// Auto-fit: zoom to show all nodes after simulation settles
const zoom = d3.zoom().scaleExtent([0.1, 4]).on('zoom', (event) => {{
  g.attr('transform', event.transform);
}});
svg.call(zoom);

function fitToView() {{
  const pad = 40;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  nodes.forEach(n => {{
    if (n.x < minX) minX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.x > maxX) maxX = n.x;
    if (n.y > maxY) maxY = n.y;
  }});
  const bw = maxX - minX + pad * 2;
  const bh = maxY - minY + pad * 2;
  const scale = Math.min(width / bw, height / bh, 2);
  const tx = width / 2 - (minX + maxX) / 2 * scale;
  const ty = height / 2 - (minY + maxY) / 2 * scale;
  svg.transition().duration(800).call(
    zoom.transform,
    d3.zoomIdentity.translate(tx, ty).scale(scale)
  );
}}

simulation.on('tick', () => {{
  link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
  node.attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
}});

// Fit view once simulation cools down
simulation.on('end', fitToView);
// Also fit after a timeout in case simulation runs long
setTimeout(fitToView, 3000);
</script>
</body>
</html>"""
    return html


def main():
    print("Generating research dashboard...")
    nodes = load_dag()
    node_index = load_node_index()
    experiments = load_experiments()
    breakthroughs = load_breakthroughs()
    papers = load_papers()
    findings_edges = load_findings_edges()

    print(f"  Nodes: {len(nodes)}")
    print(f"  Experiments: {len(experiments)}")
    print(f"  Ready nodes: {len(node_index.get('ready', []))}")

    html = generate_html(nodes, node_index, experiments, breakthroughs, papers, findings_edges)
    output = _cfg.dashboard_html
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(f"  Dashboard: {output}")
    print(f"  Open in browser: file:///{output.as_posix()}")


if __name__ == "__main__":
    main()
