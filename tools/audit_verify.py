import yaml
import argparse
import sys
import os

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

def check_deliverables():
    """
    Check if blog and arxiv deliverables exist in the current directory.
    """
    blog_found = any(f.endswith('-blog.md') for f in os.listdir('.'))
    arxiv_found = any(f.endswith('-arxiv.md') for f in os.listdir('.'))
    
    if blog_found and arxiv_found:
        return True, "Deliverables (Blog and ARXIV) found."
    else:
        return False, f"Missing deliverables: Blog={blog_found}, ARXIV={arxiv_found}."

def main():
    parser = argparse.ArgumentParser(description="Audit and verify research results.")
    parser.add_argument("--action", choices=['verify', 'report'], required=True)

    args = parser.parse_args()
    metadata = load_metadata()

    if args.action == 'verify':
        perf_ok, perf_msg = verify_performance(metadata)
        deliv_ok, deliv_msg = check_deliverables()
        
        print(f"Audit Results for {metadata['node_id']}:")
        print(f"--- Performance: {'[PASS]' if perf_ok else '[FAIL]'} {perf_msg}")
        print(f"--- Deliverables: {'[PASS]' if deliv_ok else '[FAIL]'} {deliv_msg}")
        
        if perf_ok and deliv_ok:
            print("\nRecommendation: Proceed to Human Review for merge.")
        else:
            print("\nRecommendation: Further investigation required or mark as 'discarded'.")

if __name__ == "__main__":
    main()
