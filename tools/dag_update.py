import yaml
import argparse
import sys
import os

def load_dag(path):
    if not os.path.exists(path):
        print(f"Error: DAG file not found at {path}")
        sys.exit(1)
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def save_dag(path, dag):
    with open(path, 'w') as f:
        yaml.dump(dag, f, sort_keys=False)

def add_node(dag, parent_id, hypothesis, target_improvement):
    """
    Add a new proposed node to the DAG.
    """
    # Generate new ID (H-NNN)
    existing_ids = [int(node['id'].split('-')[1]) for node in dag.get('nodes', [])]
    new_id_num = max(existing_ids) + 1 if existing_ids else 0
    new_id = f"H-{new_id_num:03d}"

    new_node = {
        'id': new_id,
        'parent': parent_id,
        'hypothesis': hypothesis,
        'status': 'pending',  # Initially pending/proposed
        'target_improvement': target_improvement,
        'actual_performance': None,
        'assigned_agent': None,
        'branch': None,
        'deliverables': {'blog': None, 'arxiv': None},
        'notes': []
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

def main():
    parser = argparse.ArgumentParser(description="Safely update the Hypothesis DAG.")
    parser.add_argument("--dag", default="docs/research/hypothesis-dag.yaml", help="Path to hypothesis-dag.yaml")
    parser.add_argument("--action", choices=['add', 'update'], required=True)
    
    # Add Node arguments
    parser.add_argument("--parent", help="Parent Node ID for 'add' action")
    parser.add_argument("--hypothesis", help="Hypothesis description for 'add' action")
    parser.add_argument("--target", type=float, help="Target improvement for 'add' action")
    
    # Update Node arguments
    parser.add_argument("--node-id", help="Node ID to update for 'update' action")
    parser.add_argument("--status", help="New status for 'update' action")
    parser.add_argument("--performance", type=float, help="Actual performance for 'update' action")

    args = parser.parse_args()
    dag = load_dag(args.dag)

    if args.action == 'add':
        if not args.parent or not args.hypothesis:
            print("Error: --parent and --hypothesis are required for 'add' action.")
            sys.exit(1)
        new_id = add_node(dag, args.parent, args.hypothesis, args.target or 0.0)
        print(f"Added new node: {new_id}")
    
    elif args.action == 'update':
        if not args.node_id or not args.status:
            print("Error: --node-id and --status are required for 'update' action.")
            sys.exit(1)
        if update_node_status(dag, args.node_id, args.status, args.performance):
            print(f"Updated node: {args.node_id}")
        else:
            print(f"Error: Node {args.node_id} not found.")
            sys.exit(1)

    save_dag(args.dag, dag)

if __name__ == "__main__":
    main()
