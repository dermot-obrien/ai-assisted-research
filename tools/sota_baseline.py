import argparse
import yaml
import sys
import os
from datetime import datetime
from openalex_discovery import search_openalex
from s2_ranking import search_semantic_scholar

def generate_sota_baseline(query, limit=10, s2_api_key=None):
    """
    Generate a SOTA baseline by combining OpenAlex and Semantic Scholar results.
    """
    print(f"--- Establishing SOTA Baseline for: '{query}' ---")
    
    # 1. Discovery (OpenAlex)
    print(f"Fetching discovery results from OpenAlex...")
    oa_results = search_openalex(query, limit)
    
    # 2. Ranking (Semantic Scholar)
    print(f"Fetching ranking results from Semantic Scholar...")
    s2_results = search_semantic_scholar(query, limit, s2_api_key)
    
    # 3. Combine and Extract Baseline
    # For simplicity, we'll pick the top paper from S2 (sorted by influential citations)
    if not s2_results:
        print("No results found in Semantic Scholar.")
        return None

    top_paper = s2_results[0]
    
    baseline = {
        'project_baseline': {
            'topic': query,
            'established_at': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            'top_paper': {
                'title': top_paper['title'],
                'authors': top_paper['authors'],
                'year': top_paper['year'],
                'url': top_paper['url'],
                'influential_citations': top_paper['influential_citations'],
                'doi': top_paper['doi']
            },
            'metric_baseline': {
                'metric': "To be extracted from abstract",
                'value': "See abstract",
                'abstract_snippet': (top_paper['abstract'][:300] + "...") if top_paper['abstract'] else "No abstract available"
            },
            'standardized_setup': {
                'dataset': {
                    'name': "TBD (e.g., Davis)",
                    'source_url': "TBD",
                    'local_path': "performance/data/{name}/"
                },
                'benchmark': {
                    'description': "Technical specification for performance measurement.",
                    'script_path': "performance/benchmarks/evaluate_{metric}.py",
                    'command': "python performance/benchmarks/evaluate_{metric}.py --input performance/data/{name}/"
                }
            }
        },
        'related_works': s2_results[1:5]
    }

    return baseline

def main():
    parser = argparse.ArgumentParser(description="Generate a SOTA baseline for research.")
    parser.add_argument("--query", required=True, help="Search query (e.g., 'GNNs in drug discovery')")
    parser.add_argument("--limit", type=int, default=10, help="Number of results to fetch (default: 10)")
    parser.add_argument("--output", help="Path to save YAML baseline (optional)")

    args = parser.parse_args()

    api_key = os.getenv('S2_API_KEY')

    baseline = generate_sota_baseline(args.query, args.limit, api_key)

    if baseline:
        if args.output:
            with open(args.output, 'w') as f:
                yaml.dump(baseline, f, sort_keys=False)
            print(f"Saved SOTA baseline to {args.output}")
        else:
            print(yaml.dump(baseline, sort_keys=False))

if __name__ == "__main__":
    main()
