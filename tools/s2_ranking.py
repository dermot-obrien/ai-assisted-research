import requests
import argparse
import yaml
import sys
import os

def search_semantic_scholar(query, limit=10, api_key=None):
    """
    Search Semantic Scholar for academic papers.
    Uses the S2AG API: https://api.semanticscholar.org/graph/v1/paper/search
    """
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        'query': query,
        'limit': limit,
        'fields': 'title,authors,year,citationCount,influentialCitationCount,abstract,url,externalIds'
    }
    
    headers = {}
    if api_key:
        headers['x-api-key'] = api_key

    try:
        response = requests.get(base_url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching from Semantic Scholar: {e}")
        sys.exit(1)

    results = []
    for paper in data.get('data', []):
        results.append({
            'paperId': paper.get('paperId'),
            'title': paper.get('title'),
            'year': paper.get('year'),
            'authors': [author.get('name') for author in paper.get('authors', [])],
            'citations': paper.get('citationCount'),
            'influential_citations': paper.get('influentialCitationCount'),
            'url': paper.get('url'),
            'doi': paper.get('externalIds', {}).get('DOI'),
            'abstract': paper.get('abstract')
        })

    # Sort by influential_citations (SOTA ranking)
    results.sort(key=lambda x: (x['influential_citations'] or 0), reverse=True)

    return results

def main():
    parser = argparse.ArgumentParser(description="Rank academic research via Semantic Scholar API.")
    parser.add_argument("--query", required=True, help="Search query (e.g., 'GNNs in drug discovery')")
    parser.add_argument("--limit", type=int, default=10, help="Number of results to fetch (default: 10)")
    parser.add_argument("--api-key", help="Semantic Scholar API key (optional)")
    parser.add_argument("--output", help="Path to save YAML output (optional)")

    args = parser.parse_args()

    api_key = args.api_key or os.getenv('S2_API_KEY')

    print(f"Searching Semantic Scholar for: '{args.query}'...")
    results = search_semantic_scholar(args.query, args.limit, api_key)

    if args.output:
        with open(args.output, 'w') as f:
            yaml.dump(results, f, sort_keys=False)
        print(f"Saved {len(results)} results to {args.output}")
    else:
        print(yaml.dump(results, sort_keys=False))

if __name__ == "__main__":
    main()
