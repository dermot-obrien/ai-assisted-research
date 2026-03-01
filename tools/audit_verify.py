import yaml
import argparse
import sys
import os
import subprocess
import shutil

def run_command(command):
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command '{command}': {e.stderr}")
        return None

def load_metadata(path='metadata.yaml'):
    if not os.path.exists(path):
        print(f"Error: metadata.yaml not found at {path}")
        sys.exit(1)
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def verify_performance(metadata):
    """
    Verify if actual performance is recorded and compares correctly with parent.
    Default: Minimize (MSE, Loss). Change logic for maximize (Accuracy, F1).
    """
    actual = metadata.get('actual_performance')
    parent = metadata.get('parent_performance')
    
    if actual is None:
        return False, "Error: No actual performance recorded."
    
    # Minimize logic for simulation (MSE)
    if actual < parent:
        return True, f"Success: Performance improved from {parent} to {actual}."
    else:
        return False, f"Warning: Performance did not improve ({actual} >= {parent})."

def check_deliverables(metadata):
    """
    Check if blog, arxiv, or pivot deliverables exist in the current directory.
    """
    blog_found = any(f.endswith('-blog.md') for f in os.listdir('.'))
    arxiv_found = any(f.endswith('-arxiv.md') for f in os.listdir('.'))
    pivot_found = any(f.endswith('-pivot.md') for f in os.listdir('.'))
    
    if blog_found and arxiv_found:
        return True, "Deliverables (Blog and ARXIV) found."
    elif pivot_found:
        return True, "Deliverables (Pivot Report) found for ineffective node."
    else:
        return False, f"Missing deliverables: Blog={blog_found}, ARXIV={arxiv_found}, Pivot={pivot_found}."

def clean_room_check():
    """
    Ensure the benchmark script being run is identical to the one in the main branch.
    Prevents 'Worker Bias' where the evaluation script was altered to pass.
    """
    benchmark_dir = "performance/benchmarks"
    if not os.path.exists(benchmark_dir):
        return False, f"Benchmark directory {benchmark_dir} not found. Cannot verify clean room."
        
    print("Executing Clean Room verification against 'main' branch...")
    
    # Check if git is available and dirty
    status = run_command("git status --porcelain")
    if status is None:
        return False, "Git command failed."
        
    # We compare the tree of the benchmarks folder with main
    diff = run_command(f"git diff main -- {benchmark_dir}")
    if diff:
        return False, f"Clean Room Failure: The benchmark scripts in {benchmark_dir} have been modified compared to the 'main' branch. Audit rejected."
        
    return True, "Clean Room Verified: Benchmark scripts match 'main'."

def main():
    parser = argparse.ArgumentParser(description="Audit and verify research results.")
    parser.add_argument("--action", choices=['verify', 'report'], required=True)
    parser.add_argument("--clean-room", action="store_true", help="Enforce Clean Room verification against main branch")

    args = parser.parse_args()
    metadata = load_metadata()

    if args.action == 'verify':
        print(f"Starting Audit for {metadata['node_id']}...\n")
        
        clean_ok = True
        clean_msg = "Clean room check bypassed."
        if args.clean_room:
            clean_ok, clean_msg = clean_room_check()
            
        perf_ok, perf_msg = verify_performance(metadata)
        deliv_ok, deliv_msg = check_deliverables(metadata)
        
        print(f"Audit Results:")
        print(f"--- Environment:  {'[PASS]' if clean_ok else '[FAIL]'} {clean_msg}")
        print(f"--- Performance:  {'[PASS]' if perf_ok else '[FAIL]'} {perf_msg}")
        print(f"--- Deliverables: {'[PASS]' if deliv_ok else '[FAIL]'} {deliv_msg}")
        
        if perf_ok and deliv_ok and clean_ok:
            print("\nRecommendation: Proceed to Human Review for merge.")
        elif deliv_ok and clean_ok and not perf_ok:
            print("\nRecommendation: Pivot report generated. Proceed to Human Review to mark as 'ineffective'.")
        else:
            print("\nRecommendation: Audit FAILED. Further investigation required. Do not merge.")
            sys.exit(1)

if __name__ == "__main__":
    main()
