import os
import subprocess
import yaml
import argparse
import sys

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command '{command}': {e.stderr}")
        return None

def create_research_branch(node_id, topic):
    """
    Create a new research branch for a specific node ID and topic.
    """
    branch_name = f"research/{node_id}-{topic.replace(' ', '-').lower()}"
    print(f"Creating branch: {branch_name}")
    
    # Check if branch exists
    if run_command(f"git rev-parse --verify {branch_name}"):
        print(f"Branch {branch_name} already exists. Checking it out...")
        run_command(f"git checkout {branch_name}")
    else:
        run_command(f"git checkout -b {branch_name}")
    
    return branch_name

def init_metadata(node_id, branch_name, agent_id, role, parent_perf, target_imp):
    """
    Initialize metadata.yaml for the current branch in docs/research/H-{ID}/.
    """
    node_dir = os.path.join('docs', 'research', node_id)
    if not os.path.exists(node_dir):
        os.makedirs(node_dir)

    metadata = {
        'node_id': node_id,
        'branch_name': branch_name,
        'status': 'in_progress',
        'current_owner': {
            'id': agent_id,
            'session_id': os.getenv('SESSION_ID', 'S-000'),
            'role': role
        },
        'parent_performance': parent_perf,
        'target_improvement': target_imp,
        'actual_performance': None,
        'handoff': {
            'next_role': None,
            'instructions': None,
            'timestamp': "2026-02-28T10:00:00Z"
        },
        'milestones': [
            {'id': 'baseline', 'status': 'pending'},
            {'id': 'implementation', 'status': 'pending'},
            {'id': 'benchmarking', 'status': 'pending'},
            {'id': 'synthesis', 'status': 'pending'}
        ]
    }
    
    metadata_path = os.path.join(node_dir, 'metadata.yaml')
    with open(metadata_path, 'w') as f:
        yaml.dump(metadata, f, sort_keys=False)
    
    print(f"Initialized metadata.yaml for {node_id} in {node_dir}")

def main():
    parser = argparse.ArgumentParser(description="Manage research branches and metadata.")
    parser.add_argument("--action", choices=['init', 'handoff'], required=True)
    
    # Init arguments
    parser.add_argument("--node-id", help="Node ID (e.g., H-001)")
    parser.add_argument("--topic", help="Research topic for branch name")
    parser.add_argument("--agent-id", help="ID of the current agent")
    parser.add_argument("--role", default='worker', help="Role of the current agent")
    parser.add_argument("--parent-perf", type=float, default=0.0)
    parser.add_argument("--target-imp", type=float, default=0.0)

    # Handoff arguments
    parser.add_argument("--next-role", help="Next agent role in the sequence")
    parser.add_argument("--instructions", help="Handoff instructions")
    parser.add_argument("--performance", type=float, help="Actual performance recorded")

    args = parser.parse_args()

    if args.action == 'init':
        if not args.node_id or not args.topic or not args.agent_id:
            print("Error: --node-id, --topic, and --agent-id are required for 'init' action.")
            sys.exit(1)
        
        branch_name = create_research_branch(args.node_id, args.topic)
        init_metadata(args.node_id, branch_name, args.agent_id, args.role, args.parent_perf, args.target_imp)
        
        # Initial commit
        node_dir = os.path.join('docs', 'research', args.node_id)
        metadata_path = os.path.join(node_dir, 'metadata.yaml')
        run_command(f"git add {metadata_path}")
        run_command(f'git commit -m "[INIT: {args.role}] Starting work on {args.node_id}"')
        print(f"Branch {branch_name} initialized and pushed.")

    elif args.action == 'handoff':
        node_id = args.node_id
        if not node_id:
            print("Error: --node-id is required for 'handoff' action.")
            sys.exit(1)
            
        node_dir = os.path.join('docs', 'research', node_id)
        metadata_path = os.path.join(node_dir, 'metadata.yaml')
        
        if not os.path.exists(metadata_path):
            print(f"Error: metadata.yaml not found at {metadata_path}")
            sys.exit(1)
            
        with open(metadata_path, 'r') as f:
            metadata = yaml.safe_load(f)
            
        metadata['status'] = 'awaiting_review' if args.next_role == 'auditor' else 'in_progress'
        metadata['handoff']['next_role'] = args.next_role
        metadata['handoff']['instructions'] = args.instructions
        metadata['handoff']['timestamp'] = "2026-02-28T10:05:00Z"
        if args.performance is not None:
            metadata['actual_performance'] = args.performance
            
        with open(metadata_path, 'w') as f:
            yaml.dump(metadata, f, sort_keys=False)
            
        run_command(f"git add {metadata_path}")
        run_command(f'git commit -m "[HANDOFF: {args.next_role}] {args.instructions[:50]}..."')
        print(f"Handoff complete. Next role: {args.next_role}")

if __name__ == "__main__":
    main()
