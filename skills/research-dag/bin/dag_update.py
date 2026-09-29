# SPDX-FileCopyrightText: 2026 Dermot O'Brien
# SPDX-License-Identifier: Apache-2.0
"""
Change the hypothesis DAG safely.

With dag_store and dag_project set in research.yaml, every change is written as
events to the shared DAG store (see dag_store.py): the store is pulled first,
the change is diffed into events, pushed with a retry when someone else pushed
first, and the YAML at dag_path is regenerated from the replay. Without them,
the change is made to the YAML file directly, as it always was.
"""
import yaml
import argparse
import copy
import re
import sys
import os
import time

class DAGLock:
    """Cross-platform atomic file lock for the DAG."""
    def __init__(self, path):
        self.lock_path = path + ".lock"
    
    def __enter__(self):
        for _ in range(20):
            try:
                # O_CREAT | O_EXCL ensures atomic file creation. Fails if exists.
                self.fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                return self
            except FileExistsError:
                time.sleep(0.5)
        raise TimeoutError(f"Could not acquire DAG lock at {self.lock_path}. Another agent might be updating it.")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        os.close(self.fd)
        try:
            os.remove(self.lock_path)
        except OSError:
            pass

def load_dag(path):
    if not os.path.exists(path):
        print(f"Error: DAG file not found at {path}")
        sys.exit(1)
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def save_dag(path, dag):
    with open(path, 'w') as f:
        yaml.dump(dag, f, sort_keys=False)

def next_node_id(nodes, parent_id):
    """The id for a new node under parent_id.

    A flat DAG (every id H-NNN) keeps sequential numbering: the highest number
    plus one. A DAG with hierarchical ids (H-204.4.25) numbers a child under its
    parent instead; see hierarchical_child_id.
    """
    try:
        existing_ids = [int(node['id'].split('-')[1]) for node in nodes]
    except (ValueError, IndexError):
        return hierarchical_child_id([node['id'] for node in nodes], parent_id)
    new_id_num = max(existing_ids) + 1 if existing_ids else 0
    return f"H-{new_id_num:03d}"


def hierarchical_child_id(ids, parent_id):
    """The next child id under parent_id in a DAG with hierarchical ids.

    - A parent with dotted children (H-204.4.1 to H-204.4.25) gets the next one,
      H-204.4.26. A letter-suffixed sibling (H-204.4.8a) counts as its number.
    - A block parent, H-N00, with no dotted children takes the next free flat id
      in its block (H-700 with H-701 to H-704 gets H-705). The root, H-000, takes
      the next free block (H-900).
    - Any other parent starts a dotted level: H-204 gets H-204.1.
    """
    taken = set(ids)
    if parent_id not in taken:
        raise ValueError(f"Parent {parent_id} is not in the DAG.")
    kids = re.compile(re.escape(parent_id) + r"\.(\d+)[a-z]?$")
    numbers = [int(m.group(1)) for i in ids if (m := kids.match(i))]
    if numbers:
        n = max(numbers) + 1
        while f"{parent_id}.{n}" in taken:
            n += 1
        return f"{parent_id}.{n}"
    block = re.match(r"^(.*-)(\d+)$", parent_id)
    if block and int(block.group(2)) % 100 == 0:
        head, width, base = block.group(1), len(block.group(2)), int(block.group(2))
        flat = re.compile(re.escape(head) + r"(\d+)$")
        used = [int(m.group(1)) for i in ids if (m := flat.match(i)) and len(m.group(1)) == width]
        if base == 0:
            candidates = range(100, 10 ** width, 100)
            used = [u for u in used if u % 100 == 0 and u > 0]
        else:
            candidates = range(base + 1, base + 100)
            used = [u for u in used if base < u < base + 100]
        highest = max(used, default=base)
        for n in candidates:
            if n > highest and f"{head}{n:0{width}d}" not in taken:
                return f"{head}{n:0{width}d}"
    n = 1
    while f"{parent_id}.{n}" in taken:
        n += 1
    return f"{parent_id}.{n}"


def add_node(dag, parent_id, hypothesis, target_improvement, metric=None):
    """
    Add a new proposed node to the DAG.
    """
    # Validate metric consistency
    primary_metric = dag.get('metadata', {}).get('primary_metric')
    if metric and primary_metric and metric.lower() != primary_metric.lower():
        print(f"Warning: Proposed metric '{metric}' differs from DAG's primary metric '{primary_metric}'.")
    
    new_id = next_node_id(dag.get('nodes', []), parent_id)

    new_node = {
        'id': new_id,
        'parent': parent_id,
        'hypothesis': hypothesis,
        'status': 'pending',  # Initially pending/proposed
        'target_improvement': target_improvement,
        'metric': metric or primary_metric or "Unknown",
        'actual_performance': None,
        'assigned_agent': None,
        'branch': None,
        'deliverables': {'blog': None, 'arxiv': None, 'pivot': None},
        'notes': [],
        # Second axis: status says whether it is true, adoption says whether it
        # is live. See docs/adoption-and-drift.md.
        'adoption': {
            'state': 'not_assessed',
            'artefact': None,
            'verification': None,
            'verified_on': None,
            'note': None,
        },
        'blocked_by': [],
        'contested_by': [],
    }

    dag['nodes'].append(new_node)
    
    # Update parent's avenues list
    for node in dag['nodes']:
        if node['id'] == parent_id:
            if 'avenues' not in node:
                node['avenues'] = []
            if new_id not in node['avenues']:
                node['avenues'].append(new_id)
            break

    return new_id

def update_node_status(dag, node_id, status, actual_performance=None):
    """
    Update the status and performance of an existing node.
    """
    for node in dag['nodes']:
        if node['id'] == node_id:
            node['status'] = status
            if actual_performance is not None:
                node['actual_performance'] = actual_performance
            return True
    return False

ADOPTION_STATES = ['not_assessed', 'not_applicable', 'not_adopted',
                   'partial', 'adopted', 'contradicted']

# States that assert something about the running system, so they owe a predicate.
CLAIMS_REALITY = {'adopted', 'partial', 'contradicted'}


def update_node_adoption(dag, node_id, state, artefact=None, verification=None, note=None):
    """
    Set a node's adoption state: whether the finding is live, as distinct from
    whether it is true. See docs/adoption-and-drift.md.
    """
    import datetime
    for node in dag['nodes']:
        if node['id'] == node_id:
            ad = node.get('adoption') or {}
            ad['state'] = state
            if artefact is not None:
                ad['artefact'] = artefact
            if verification is not None:
                ad['verification'] = verification
            if note is not None:
                ad['note'] = note
            ad['verified_on'] = datetime.date.today().isoformat()
            node['adoption'] = ad

            if state in CLAIMS_REALITY and not ad.get('verification'):
                print(f"Warning: {node_id} claims '{state}' with no --verification predicate. "
                      f"Claiming adoption is not demonstrating it; reconcile.py will report it "
                      f"as unverified.")
            return True
    return False


def find_node(dag, node_id):
    for node in dag.get('nodes', []):
        if node['id'] == node_id:
            return node
    return None


def relink_node(dag, node_id, new_parent):
    """Move a node under another parent, keeping the parents' avenues in step."""
    node = find_node(dag, node_id)
    if node is None:
        return f"Error: Node {node_id} not found."
    if find_node(dag, new_parent) is None:
        return f"Error: Parent {new_parent} not found."
    cur = new_parent
    while cur is not None:
        if cur == node_id:
            return f"Error: Cannot move {node_id} under its own descendant {new_parent}."
        parent = find_node(dag, cur)
        cur = parent.get('parent') if parent else None
    old_parent = node.get('parent')
    node['parent'] = new_parent
    old = find_node(dag, old_parent) if old_parent else None
    if old and isinstance(old.get('avenues'), list) and node_id in old['avenues']:
        old['avenues'] = [a for a in old['avenues'] if a != node_id]
    new = find_node(dag, new_parent)
    avenues = new.get('avenues') or []
    if node_id not in avenues:
        new['avenues'] = [*avenues, node_id]
    return None


PROTECTED_FIELDS = {'id': 'ids never change', 'parent': 'use --action relink'}


def set_node_field(dag, node_id, field, value):
    """Set any one field of a node. The value is parsed as YAML, so 0.07, [a, b] and null work."""
    if field in PROTECTED_FIELDS:
        return f"Error: Cannot set '{field}': {PROTECTED_FIELDS[field]}."
    node = find_node(dag, node_id)
    if node is None:
        return f"Error: Node {node_id} not found."
    node[field] = value
    return None


def add_note(dag, node_id, text):
    """Append a note: a new item when notes is a list, a new line when it is text."""
    node = find_node(dag, node_id)
    if node is None:
        return f"Error: Node {node_id} not found."
    notes = node.get('notes')
    if isinstance(notes, list):
        node['notes'] = [*notes, text]
    elif isinstance(notes, str) and notes.strip():
        node['notes'] = notes.rstrip("\n") + "\n" + text
    else:
        node['notes'] = [text]
    return None


def apply_action(dag, args):
    """Make the requested change to dag in place. Returns (message, new node id or None).

    Exits with status 1, as before, when the request is incomplete or names a
    node that does not exist.
    """
    def fail(msg):
        print(msg)
        sys.exit(1)

    if args.action == 'add':
        if not args.parent or not args.hypothesis:
            fail("Error: --parent and --hypothesis are required for 'add' action.")
        try:
            new_id = add_node(dag, args.parent, args.hypothesis, args.target or 0.0, args.metric)
        except ValueError as e:
            fail(f"Error: {e}")
        return f"Added new node: {new_id}", new_id

    if args.action == 'adopt':
        if not args.node_id or not args.adoption:
            fail("Error: --node-id and --adoption are required for 'adopt' action.")
        if update_node_adoption(dag, args.node_id, args.adoption, args.artefact,
                                args.verification, args.adoption_note):
            return f"Set adoption of {args.node_id} to '{args.adoption}'", None
        fail(f"Error: Node {args.node_id} not found.")

    if args.action == 'update':
        if not args.node_id or not args.status:
            fail("Error: --node-id and --status are required for 'update' action.")
        if update_node_status(dag, args.node_id, args.status, args.performance):
            return f"Updated node: {args.node_id}", None
        fail(f"Error: Node {args.node_id} not found.")

    if args.action == 'relink':
        if not args.node_id or not args.parent:
            fail("Error: --node-id and --parent are required for 'relink' action.")
        err = relink_node(dag, args.node_id, args.parent)
        if err:
            fail(err)
        return f"Moved {args.node_id} under {args.parent}", None

    if args.action == 'set':
        if not args.node_id or not args.field or args.value is None:
            fail("Error: --node-id, --field and --value are required for 'set' action.")
        err = set_node_field(dag, args.node_id, args.field, yaml.safe_load(args.value))
        if err:
            fail(err)
        return f"Set {args.field} of {args.node_id}", None

    if args.action == 'note':
        if not args.node_id or not args.note:
            fail("Error: --node-id and --note are required for 'note' action.")
        err = add_note(dag, args.node_id, args.note)
        if err:
            fail(err)
        return f"Noted on {args.node_id}", None

    fail(f"Error: unknown action {args.action}")


def workspace_config():
    """research.yaml's config, or None where there is none (or it cannot be read)."""
    try:
        import rms_config
        return rms_config.load()
    except Exception:  # noqa: BLE001 - without a readable research.yaml the plain file is used
        return None


def run_in_store(store, args, view_path):
    """Pull, apply the change as events, push with retry, and regenerate the view."""
    import dag_store

    with store.lock():
        store.pull()
        state = store.replay()
        before = state.to_dag()
        after = copy.deepcopy(before)
        message, new_id = apply_action(after, args)
        bodies = dag_store.diff_events(before, after)
        if not bodies:
            store.write_view(view_path, state)
            print(f"{message} (no change)")
            return 0
        written = store.write_events(bodies)
        subject = f"{args.action} {new_id or args.node_id or ''}".strip()
        pushed = store.commit_and_push(
            f"{store.project}: {subject}",
            on_rebase=lambda: written.extend(store.resolve_collisions(written)))
        state = store.replay()
        store.write_view(view_path, state)

    for ev in written:
        final = state.add_ids.get(ev.get("eid"))
        if ev.get("type") == "add" and final not in (None, ev["id"]):
            message = (f"Added new node: {final} ({ev['id']} was taken by a concurrent writer; "
                       f"the alias is recorded)")
    print(message)
    own = {ev["eid"] for ev in written}
    for c in state.conflicts:
        if c.get("eid") in own:
            print(f"Note: {c['id']} {c['field']} was changed concurrently to "
                  f"{dag_store.short(c['replaced'], 80)}; this change replaced it.")
    if not pushed:
        print("The change is recorded in the local store only; dag_store.py sync pushes it.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Safely update the Hypothesis DAG.")
    parser.add_argument("--dag", default=None,
                        help="Path to hypothesis-dag.yaml (default: hypothesis-dag.yaml; with a DAG "
                             "store, the view at dag_path)")
    parser.add_argument("--action", choices=['add', 'update', 'adopt', 'relink', 'set', 'note'], required=True)
    parser.add_argument("--no-store", action="store_true",
                        help="Edit the YAML file directly even when research.yaml names a DAG store")
    
    # Add Node arguments (--parent is also the new parent for 'relink')
    parser.add_argument("--parent", help="Parent Node ID for 'add', new parent for 'relink'")
    parser.add_argument("--hypothesis", help="Hypothesis description for 'add' action")
    parser.add_argument("--target", type=float, help="Target improvement for 'add' action")
    parser.add_argument("--metric", help="The evaluation metric (must align with DAG primary metric)")
    
    # Update Node arguments
    parser.add_argument("--node-id", help="Node ID to change for 'update', 'adopt', 'relink', 'set' and 'note'")
    parser.add_argument("--status", choices=['pending', 'framed', 'in_progress', 'validated', 'contested', 'ineffective', 'discarded'], help="New status for 'update' action")
    parser.add_argument("--performance", type=float, help="Actual performance for 'update' action")

    # Adoption arguments — the second axis (is it live?), see docs/adoption-and-drift.md
    parser.add_argument("--adoption", choices=ADOPTION_STATES, help="Adoption state for 'adopt' action")
    parser.add_argument("--artefact", help="Path or symbol in the running system that would carry this finding")
    parser.add_argument("--verification", help="Shell predicate that exits 0 while the claim still holds")
    parser.add_argument("--adoption-note", help="Why the node sits at this adoption state")

    # Any other field, and notes
    parser.add_argument("--field", help="Field to set for 'set' action (not id or parent)")
    parser.add_argument("--value", help="Value for 'set' action, parsed as YAML")
    parser.add_argument("--note", help="Text to append to the node's notes for 'note' action")

    args = parser.parse_args()
    
    cfg = None if args.no_store else workspace_config()
    if cfg is not None and bool(cfg.dag_store) != bool(cfg.dag_project):
        print("Warning: research.yaml sets only one of dag_store and dag_project; "
              "editing the YAML file directly.")
    if cfg is not None and cfg.uses_dag_store:
        import dag_store
        try:
            store = dag_store.DagStore.from_config(cfg)
            store.ensure()
            sys.exit(run_in_store(store, args, args.dag or cfg.dag_path))
        except (dag_store.StoreError, TimeoutError) as e:
            print(f"Error: {e}")
            sys.exit(1)

    args.dag = args.dag or "hypothesis-dag.yaml"
    with DAGLock(args.dag):
        dag = load_dag(args.dag)
        message, _ = apply_action(dag, args)
        print(message)
        save_dag(args.dag, dag)

if __name__ == "__main__":
    main()
