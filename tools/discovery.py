import os
import sys
import yaml
import subprocess

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        return ""

def excavate_workspace():
    """
    Analyze the workspace to identify research markers.
    """
    findings = {
        'potential_objectives': [],
        'potential_metrics': [],
        'existing_strands': [],
        'git_history_summary': ""
    }

    # 1. Search for Objectives in README/Docs
    readme = run_command("grep -i \"objective\\|goal\\|hypothesis\" README.md")
    if readme: findings['potential_objectives'].append(readme)

    # 2. Search for Metrics in src/performance
    metrics = run_command("grep -r \"MSE\\|AUROC\\|accuracy\\|F1\" src/ performance/")
    if metrics: findings['potential_metrics'].append(metrics[:500] + "...")

    # 3. Analyze Git History for 'Research' markers
    git_log = run_command("git log --oneline -n 10")
    findings['git_history_summary'] = git_log

    return findings

def reconstruct_dag(findings):
    """
    Heuristically reconstruct the starting nodes.
    """
    print("\n--- Discovery Agent: Reconstructing Hypothesis DAG ---")
    print(f"Objective Found: {findings['potential_objectives'][:1] or 'Unknown'}")
    
    # Heuristic Root Node
    root_node = {
        'id': 'H-000',
        'hypothesis': "Original project baseline (Extracted from workspace history).",
        'status': 'completed',
        'performance': "TBD (Requires human input)",
        'avenues': ['H-001']
    }

    # Heuristic Current State
    current_node = {
        'id': 'H-001',
        'parent': 'H-000',
        'hypothesis': "Current implementation state.",
        'status': 'in_progress',
        'target_improvement': 0.0,
        'actual_performance': None
    }

    return [root_node, current_node]

def main():
    print("Agent: Discovery is excavating the workspace...")
    findings = excavate_workspace()
    reconstructed_nodes = reconstruct_dag(findings)

    # Initial Proposed DAG
    dag = {
        'project': {
            'name': os.path.basename(os.getcwd()),
            'objective': "Extracted from workspace analysis",
            'sota_baseline': {'external_best_performance': None, 'metric': 'TBD'}
        },
        'nodes': reconstructed_nodes
    }

    print("\n--- Proposed DAG Reconstruction ---")
    print(yaml.dump(dag, sort_keys=False))
    
    confirm = input("\nDoes this reconstruction look accurate? (yes/no): ")
    if confirm.lower() == 'yes':
        os.makedirs('docs/research', exist_ok=True)
        with open('docs/research/hypothesis-dag.yaml', 'w') as f:
            yaml.dump(dag, f, sort_keys=False)
        print("RMS Initialized in docs/research/hypothesis-dag.yaml")
    else:
        print("Initialization aborted. Please refine the analysis parameters.")

if __name__ == "__main__":
    main()
