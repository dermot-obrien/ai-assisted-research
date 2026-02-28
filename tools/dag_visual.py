#!/usr/bin/env python3
"""
Generate a radial SVG + PNG visualization of the hypothesis DAG.

Usage:
    python tools/dag_visual.py [dag_yaml_path] [output_dir]

Defaults:
    dag_yaml_path: found via research.yaml signpost
    output_dir: same directory as dag_yaml_path

Outputs:
    DAG-visual.svg  — vector graphic (primary)
    DAG-visual.png  — raster graphic converted from SVG via cairosvg
"""

import math
import sys
import os
from pathlib import Path

import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx


# === Status colours (designed for white background) ===
STATUS_COLORS = {
    'validated':   '#1a8a4a',  # dark green
    'completed':   '#27ae60',  # green
    'ineffective': '#c0392b',  # red
    'pending':     '#95a5a6',  # grey
    'in_progress': '#2980b9',  # blue
}
STATUS_BORDER = {
    'validated':   '#14693a',
    'completed':   '#1e8449',
    'ineffective': '#922b21',
    'pending':     '#7f8c8d',
    'in_progress': '#1f618d',
}
STATUS_TEXT = {
    'validated':   '#ffffff',
    'completed':   '#ffffff',
    'ineffective': '#ffffff',
    'pending':     '#ffffff',
    'in_progress': '#ffffff',
}

# === Category labels & angular ordering ===
# Alternates large/small sectors for visual balance
CATEGORY_ORDER = [
    ('H-4', 'Representation'),
    ('H-3', 'Pattern Recognition'),
    ('H-1', 'Anomaly Detection'),
    ('H-8', 'Change Point'),
    ('H-6', 'Scoring Methods'),
    ('H-7', 'Irregular TS'),
    ('H-5', 'Sequence Encoding'),
    ('H-2', 'Forecasting'),
]

# Light, pastel sector background fills
SECTOR_COLORS = {
    'H-1': '#e8f0fe',
    'H-2': '#e0f7f0',
    'H-3': '#fce4ec',
    'H-4': '#f3e5f5',
    'H-5': '#e8f5e9',
    'H-6': '#fff3e0',
    'H-7': '#e0f2f1',
    'H-8': '#fefce8',
}


def load_dag(path):
    """Load hypothesis-dag.yaml and return list of node dicts."""
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data.get('nodes', [])


def find_dag_path():
    """Find the DAG path via research.yaml signpost."""
    search = Path(__file__).resolve().parent.parent
    for _ in range(5):
        signpost = search / 'research.yaml'
        if signpost.exists():
            with open(signpost, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            dag_rel = data.get('dag_path', '')
            return str(search / dag_rel)
        search = search.parent
    return None


def truncate(text, max_len=22):
    """Truncate hypothesis text for labels."""
    if not text:
        return ''
    for sep in ['.', ' — ', ' - ', ';']:
        idx = text.find(sep)
        if 0 < idx < max_len + 5:
            text = text[:idx]
            break
    if len(text) > max_len:
        text = text[:max_len - 1] + '\u2026'
    return text


def get_category_prefix(node_id):
    """Get the H-X category prefix for a node."""
    if node_id == 'H-000':
        return 'ROOT'
    return node_id[:3]


def build_radial_positions(nodes):
    """
    Compute radial positions for all nodes.

    Layout:
    - H-000 at center
    - Category heads in inner ring
    - Leaf nodes in outer ring(s), fanning within their category sector
    - Categories with >5 children use two rings; >10 use three rings
    """
    positions = {}
    root_id = 'H-000'
    positions[root_id] = (0.0, 0.0)

    categories = {}
    category_heads = {}
    for node in nodes:
        nid = node['id']
        if nid == root_id:
            continue
        prefix = get_category_prefix(nid)
        if prefix not in categories:
            categories[prefix] = []
        if nid.endswith('00'):
            category_heads[prefix] = nid
        else:
            categories[prefix].append(nid)

    ordered_prefixes = [p for p, _ in CATEGORY_ORDER if p in category_heads]
    for p in sorted(category_heads.keys()):
        if p not in ordered_prefixes:
            ordered_prefixes.append(p)

    n_cats = len(ordered_prefixes)
    if n_cats == 0:
        return positions, ordered_prefixes, {}, {}

    child_counts = []
    for prefix in ordered_prefixes:
        count = len(categories.get(prefix, []))
        child_counts.append(max(count, 1))

    MIN_WEIGHT = 3
    weights = [max(c, MIN_WEIGHT) for c in child_counts]
    total_weight = sum(weights)

    R_CATEGORY = 6.0
    R_RING_1 = 11.5
    R_RING_2 = 16.0
    R_RING_3 = 20.5
    GAP_ANGLE = 0.10

    total_gap = GAP_ANGLE * n_cats
    available_angle = 2 * math.pi - total_gap
    current_angle = math.pi / 2

    sector_info = {}

    for i, prefix in enumerate(ordered_prefixes):
        head_id = category_heads[prefix]
        children = sorted(categories.get(prefix, []))
        n_children = len(children)

        sector_angle = available_angle * (weights[i] / total_weight)
        mid_angle = current_angle - sector_angle / 2

        sector_info[prefix] = {
            'start': current_angle,
            'end': current_angle - sector_angle,
            'mid': mid_angle,
        }

        hx = R_CATEGORY * math.cos(mid_angle)
        hy = R_CATEGORY * math.sin(mid_angle)
        positions[head_id] = (hx, hy)

        if n_children > 0:
            if n_children > 10:
                n1 = (n_children + 2) // 3
                n2 = (n_children + 2) // 3
                rings = [
                    (children[:n1], R_RING_1),
                    (children[n1:n1+n2], R_RING_2),
                    (children[n1+n2:], R_RING_3),
                ]
            elif n_children > 5:
                n1 = (n_children + 1) // 2
                rings = [
                    (children[:n1], R_RING_1),
                    (children[n1:], R_RING_2),
                ]
            else:
                rings = [(children, R_RING_1)]

            margin = sector_angle * 0.06

            for ring_children, ring_r in rings:
                if not ring_children:
                    continue
                if len(ring_children) == 1:
                    angles = [mid_angle]
                else:
                    start = current_angle - margin
                    end = current_angle - sector_angle + margin
                    angles = [start - j * (start - end) / (len(ring_children) - 1)
                              for j in range(len(ring_children))]

                for j, child_id in enumerate(ring_children):
                    cx = ring_r * math.cos(angles[j])
                    cy = ring_r * math.sin(angles[j])
                    positions[child_id] = (cx, cy)

        current_angle -= sector_angle + GAP_ANGLE

    return positions, ordered_prefixes, sector_info, category_heads


def generate_visual(nodes, output_dir):
    """Generate the radial DAG visualization as SVG, then convert to PNG."""
    node_map = {n['id']: n for n in nodes}

    G = nx.DiGraph()
    for node in nodes:
        nid = node['id']
        status = node.get('status', 'pending')
        hypothesis = node.get('hypothesis', '')
        G.add_node(nid, status=status, hypothesis=hypothesis)
        parent = node.get('parent')
        if parent:
            G.add_edge(parent, nid)

    pos, ordered_prefixes, sector_info, category_heads = build_radial_positions(nodes)
    draw_nodes = [n for n in G.nodes() if n in pos]

    # === Create figure ===
    fig, ax = plt.subplots(1, 1, figsize=(40, 40), dpi=150)
    bg_color = '#ffffff'
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    ax.set_aspect('equal')

    # === Draw sector wedges ===
    R_OUTER = 22.0
    for prefix in ordered_prefixes:
        if prefix not in sector_info:
            continue
        info = sector_info[prefix]
        sector_color = SECTOR_COLORS.get(prefix, '#f5f5f5')

        start_deg = math.degrees(info['end'])
        end_deg = math.degrees(info['start'])
        wedge = mpatches.Wedge(
            (0, 0), R_OUTER, start_deg, end_deg,
            facecolor=sector_color, edgecolor='none',
            alpha=0.7, zorder=0
        )
        ax.add_patch(wedge)

        # Sector boundary lines
        for angle in [info['start'], info['end']]:
            x_end = R_OUTER * math.cos(angle)
            y_end = R_OUTER * math.sin(angle)
            ax.plot([0, x_end], [0, y_end], color='#d0d0d0', lw=0.8, alpha=0.6, zorder=1)

    # === Draw concentric guide rings ===
    for r in [6.0, 11.5, 16.0, 20.5]:
        ring = plt.Circle((0, 0), r, fill=False, edgecolor='#d5d5d5',
                          linewidth=0.6, alpha=0.5, linestyle=':', zorder=1)
        ax.add_patch(ring)

    # === Draw edges ===
    for u, v in G.edges():
        if u in pos and v in pos:
            x0, y0 = pos[u]
            x1, y1 = pos[v]

            if u == 'H-000':
                lw, alpha, color = 1.8, 0.5, '#8888aa'
            else:
                lw, alpha, color = 1.0, 0.35, '#aaaacc'

            ax.annotate('',
                xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(
                    arrowstyle='-|>',
                    color=color,
                    lw=lw,
                    alpha=alpha,
                    connectionstyle='arc3,rad=0.08',
                    mutation_scale=12,
                ),
            )

    # === Draw nodes ===
    for nid in draw_nodes:
        x, y = pos[nid]
        node_data = node_map.get(nid, {})
        status = node_data.get('status', 'pending')
        hypothesis = node_data.get('hypothesis', '')

        fill = STATUS_COLORS.get(status, '#95a5a6')
        border = STATUS_BORDER.get(status, '#7f8c8d')
        text_color = STATUS_TEXT.get(status, '#ffffff')

        if nid == 'H-000':
            node_r = 2.4
            circle = plt.Circle((x, y), node_r,
                                facecolor=fill, edgecolor=border,
                                linewidth=3.0, alpha=0.95, zorder=10)
            ax.add_patch(circle)
            # Subtle glow
            glow = plt.Circle((x, y), node_r * 1.25,
                              facecolor='none', edgecolor=fill,
                              linewidth=2.0, alpha=0.25, zorder=9)
            ax.add_patch(glow)
            ax.text(x, y + 0.5, 'H-000', ha='center', va='center',
                    fontsize=16, fontweight='bold', color=text_color, zorder=11,
                    fontfamily='Calibri')
            ax.text(x, y - 0.7, 'GIFS for Irregular\nTime Series',
                    ha='center', va='center',
                    fontsize=10, color='#e8e8e8', zorder=11,
                    fontfamily='Calibri', linespacing=1.2)

        elif nid.endswith('00'):
            node_r = 1.7
            circle = plt.Circle((x, y), node_r,
                                facecolor=fill, edgecolor=border,
                                linewidth=2.5, alpha=0.95, zorder=8)
            ax.add_patch(circle)
            prefix = get_category_prefix(nid)
            cat_label = next((lbl for p, lbl in CATEGORY_ORDER if p == prefix), nid)
            ax.text(x, y + 0.35, nid, ha='center', va='center',
                    fontsize=12, fontweight='bold', color=text_color, zorder=9,
                    fontfamily='Calibri')
            ax.text(x, y - 0.55, cat_label, ha='center', va='center',
                    fontsize=8, color='#e8e8e8', zorder=9,
                    fontfamily='Calibri')

        else:
            node_r = 1.15
            circle = plt.Circle((x, y), node_r,
                                facecolor=fill, edgecolor=border,
                                linewidth=1.8, alpha=0.92, zorder=6)
            ax.add_patch(circle)

            short = truncate(hypothesis, 18)
            if short:
                ax.text(x, y + 0.2, nid, ha='center', va='center',
                        fontsize=8, fontweight='bold', color=text_color, zorder=7,
                        fontfamily='Calibri')
                ax.text(x, y - 0.35, short, ha='center', va='center',
                        fontsize=4.5, color='#e8e8e8', zorder=7,
                        fontfamily='Calibri', alpha=0.95)
            else:
                ax.text(x, y, nid, ha='center', va='center',
                        fontsize=8, fontweight='bold', color=text_color, zorder=7,
                        fontfamily='Calibri')

    # === Category sector labels (outer ring) ===
    R_LABEL = 24.0
    for prefix in ordered_prefixes:
        if prefix not in sector_info:
            continue
        info = sector_info[prefix]
        mid_angle = info['mid']

        cat_label = next((lbl for p, lbl in CATEGORY_ORDER if p == prefix), prefix)

        lx = R_LABEL * math.cos(mid_angle)
        ly = R_LABEL * math.sin(mid_angle)

        angle_deg = math.degrees(mid_angle) % 360
        if angle_deg > 90 and angle_deg < 270:
            rotation = angle_deg + 180
        else:
            rotation = angle_deg

        ax.text(lx, ly, cat_label.upper(), ha='center', va='center',
                fontsize=14, fontweight='bold', color='#444466',
                fontfamily='Calibri', alpha=1.0,
                rotation=rotation,
                rotation_mode='anchor',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#ffffff',
                          edgecolor='#9999bb', alpha=0.95, linewidth=1.2))

    # === Title ===
    ax.text(0, -26.5, 'GIFS Research Hypothesis DAG',
            ha='center', va='center',
            fontsize=26, fontweight='bold', color='#2c3e50',
            fontfamily='Calibri')
    ax.text(0, -28.2, 'Initiative IN-001  \u00b7  Irregular Time Series Analysis',
            ha='center', va='center',
            fontsize=14, color='#7f8c8d',
            fontfamily='Calibri')

    # === Legend ===
    legend_y = -24.5
    legend_x = -22.0
    legend_items = [
        ('Validated', STATUS_COLORS['validated']),
        ('Completed', STATUS_COLORS['completed']),
        ('Ineffective', STATUS_COLORS['ineffective']),
        ('Pending', STATUS_COLORS['pending']),
        ('In Progress', STATUS_COLORS['in_progress']),
    ]
    for i, (label, color) in enumerate(legend_items):
        y = legend_y - i * 1.2
        circle = plt.Circle((legend_x, y), 0.45, facecolor=color,
                            edgecolor=STATUS_BORDER.get(label.lower().replace(' ', '_'), '#666'),
                            linewidth=1.0, zorder=5)
        ax.add_patch(circle)
        ax.text(legend_x + 0.9, y, label, ha='left', va='center',
                fontsize=11, color='#2c3e50', fontfamily='Calibri', zorder=5)

    # === Stats ===
    status_counts = {}
    for node in nodes:
        s = node.get('status', 'pending')
        status_counts[s] = status_counts.get(s, 0) + 1

    stats_x = 22.0
    ax.text(stats_x, legend_y, f'{len(nodes)} hypotheses', ha='right', va='center',
            fontsize=12, fontweight='bold', color='#2c3e50', fontfamily='Calibri')
    for i, (status, count) in enumerate(sorted(status_counts.items())):
        y = legend_y - (i + 1) * 1.2
        ax.text(stats_x, y, f'{status}: {count}', ha='right', va='center',
                fontsize=11, color=STATUS_COLORS.get(status, '#95a5a6'),
                fontfamily='Calibri', fontweight='bold')

    # === Set limits ===
    ax.set_xlim(-28, 28)
    ax.set_ylim(-31, 27)
    ax.axis('off')

    # === Save SVG ===
    svg_path = os.path.join(output_dir, 'DAG-visual.svg')
    plt.tight_layout(pad=0.5)
    plt.savefig(svg_path, format='svg', facecolor=fig.get_facecolor(),
                bbox_inches='tight', pad_inches=0.5)
    plt.close(fig)
    print(f'SVG written to: {svg_path}')

    # === Convert SVG to PNG via cairosvg ===
    png_path = os.path.join(output_dir, 'DAG-visual.png')
    try:
        import cairo as _pycairo
        sys.modules.setdefault('cairocffi', _pycairo)
        import cairosvg
        with open(svg_path, 'rb') as f:
            svg_data = f.read()
        cairosvg.svg2png(bytestring=svg_data, write_to=png_path,
                         output_width=4000, output_height=4000)
        print(f'PNG written to: {png_path}')
    except Exception as e:
        print(f'PNG conversion failed ({e}), falling back to matplotlib render')
        # Re-render directly as PNG
        fig2, ax2 = _rebuild_figure(nodes, pos, ordered_prefixes, sector_info,
                                     category_heads, draw_nodes, G, node_map)
        fig2.savefig(png_path, format='png', facecolor=fig2.get_facecolor(),
                     bbox_inches='tight', pad_inches=0.5, dpi=150)
        plt.close(fig2)
        print(f'PNG written to: {png_path} (matplotlib fallback)')

    n_edges = sum(1 for n in nodes if n.get('parent'))
    print(f'Nodes: {len(nodes)}, Edges: {n_edges}')


def main():
    if len(sys.argv) > 1:
        dag_path = sys.argv[1]
    else:
        dag_path = find_dag_path()
        if not dag_path:
            print('Error: Could not find DAG. Pass path as argument or ensure research.yaml exists.')
            sys.exit(1)

    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    else:
        output_dir = str(Path(dag_path).parent)

    print(f'Loading DAG from: {dag_path}')
    nodes = load_dag(dag_path)
    print(f'Loaded {len(nodes)} nodes')

    generate_visual(nodes, output_dir)


if __name__ == '__main__':
    main()
