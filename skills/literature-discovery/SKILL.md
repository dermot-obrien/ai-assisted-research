---
name: literature-discovery
description: "Search the scholarly literature and establish the state of the art for a question: find papers through OpenAlex, rank them by citations through Semantic Scholar, and combine both into a state-of-the-art baseline with the best published results and their citations. Use when asked to search the literature, find related work or prior art, establish the state of the art or a baseline for a research question, or rank papers on a topic."
license: CC-BY-4.0 AND Apache-2.0. Instructions under CC BY 4.0, code under Apache-2.0; see the repository's LICENSE.
compatibility: Python 3.10 or newer with requests and PyYAML (requirements.txt). Needs network access to api.openalex.org and api.semanticscholar.org. OPENALEX_EMAIL and S2_API_KEY are optional and raise the rate limits.
metadata:
  author: dermot-obrien
  version: "1.1.1"
  homepage: https://github.com/dermot-obrien/ai-assisted-research
  x-skill-requires: ""
---

# Literature Discovery

Finds what has already been published on a question, and what the best published result is. It is the evidence behind a claim about the state of the art: a number with a citation, not an impression of one.

`<skills>` below is the directory this skill is installed in. Install the two dependencies once with `pip install -r <skills>/literature-discovery/requirements.txt`.

## Tools

| Task | Command |
|---|---|
| Find papers on a topic | `python <skills>/literature-discovery/bin/openalex_discovery.py --query "<topic>" --limit 10 --output papers.yaml` |
| Rank papers by influence | `python <skills>/literature-discovery/bin/s2_ranking.py --query "<topic>" --limit 10 --output ranked.yaml` |
| Establish a state-of-the-art baseline | `python <skills>/literature-discovery/bin/sota_baseline.py --query "<topic>" --limit 10 --output baseline.yaml` |

`sota_baseline.py` combines the other two: OpenAlex for breadth, Semantic Scholar for citation-based ranking. Every tool prints its options with `--help` and writes YAML when given `--output`.

## Rate limits and keys

Both services are free and rate-limited. Set `OPENALEX_EMAIL` to an address you read, which places requests in OpenAlex's polite pool, and `S2_API_KEY` to a Semantic Scholar key if you have one; `s2_ranking.py` also takes `--api-key`. Never write either into a repository.

## Using the results

- Record the best published result for the metric that matters, with its citation. Where papers report different metrics, say so rather than converting between them.
- Search results are a starting point, not a literature review. Read the abstracts of what ranks highest before you cite it, and say which query produced the baseline, so it can be repeated.
- A result the tools cannot find is not evidence that none exists. Say what was searched.

## Related

- `aar-start-research`, in this bundle, uses this skill to baseline the state of the art before it designs the hypothesis DAG. Nothing else in this bundle is needed to use it.
