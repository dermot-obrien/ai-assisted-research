import os
import requests
import argparse
import yaml
import sys

def search_openalex(query, limit=10):
    """
    Search OpenAlex for academic works.
    Uses the OpenAlex API: https://api.openalex.org/works
    """
    base_url = "https://api.openalex.org/works"
    params = {
        'filter': f'default.search:{query}',
        'per_page': limit,
        'sort': 'relevance_score:desc',
        'mailto': os.environ.get('OPENALEX_EMAIL', 'user@example.com')  # OpenAlex "Polite Pool" - set OPENALEX_EMAIL env var
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching from OpenAlex: {e}")
        sys.exit(1)

    results = []
    for work in data.get('results', []):
        results.append({
            'id': work.get('id'),
            'title': work.get('title'),
            'display_name': work.get('display_name'),
            'publication_year': work.get('publication_year'),
            'authors': [author.get('author', {}).get('display_name') for author in work.get('authorships', [])],
            'citations': work.get('cited_by_count'),
            'relevance_score': work.get('relevance_score'),
            'doi': work.get('doi'),
            'abstract_inverted_index': work.get('abstract_inverted_index'),
            'open_access': work.get('open_access', {}).get('is_oa')
        })

    return results

def main():
    parser = argparse.ArgumentParser(description="Discover academic research via OpenAlex API.")
    parser.add_argument("--query", required=True, help="Search query (e.g., 'GNNs in drug discovery')")
    parser.add_argument("--limit", type=int, default=10, help="Number of results to fetch (default: 10)")
    parser.add_argument("--output", help="Path to save YAML output (optional)")

    args = parser.parse_args()

    print(f"Searching OpenAlex for: '{args.query}'...")
    results = search_openalex(args.query, args.limit)

    if args.output:
        with open(args.output, 'w') as f:
            yaml.dump(results, f, sort_keys=False)
        print(f"Saved {len(results)} results to {args.output}")
    else:
        print(yaml.dump(results, sort_keys=False))

if __name__ == "__main__":
    main()
