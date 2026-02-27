# Deliverable: WI-001-D02 Academic API Integration

> Activity: WI-001-A2 Academic API Integration
> Status: Complete

## Overview

This deliverable implements the integration logic for academic source APIs, enabling agents to baseline the "State of the Art" (SOTA).

## 1. OpenAlex Discovery Tool (`tools/openalex_discovery.py`)

A robust Python tool for broad discovery of academic research via the OpenAlex API.

### Features
- **Semantic Search**: Uses OpenAlex's `/find/works` endpoint.
- **Metadata Extraction**: Fetches titles, authors, citations, and abstracts.
- **Output**: Generates a YAML summary of the top 10-20 relevant papers.

### Usage
```bash
python tools/openalex_discovery.py --query "GNNs in drug discovery" --limit 10
```

## 2. Semantic Scholar Ranking Tool (`tools/s2_ranking.py`)

A specialized Python tool for deep citation analysis and ranking using the Semantic Scholar (S2AG) API.

### Features
- **Influential Citations**: Distinguishes between casual mentions and papers that significantly build upon previous work.
- **Paper Search**: Fetches metadata, abstracts, and citations for specific DOIs or search terms.
- **Ranking**: Ranks findings by influence and citation count.

### Usage
```bash
python tools/s2_ranking.py --query "GNNs in drug discovery" --limit 10
```

## 3. SOTA Baseline Generator (`tools/sota_baseline.py`)

An orchestrator script that combines discovery and ranking to establish a "State of the Art" baseline for a new research project.

### Features
- **Discovery + Ranking**: Uses both OpenAlex and Semantic Scholar APIs.
- **Baseline Extraction**: Identifies the top paper and its associated performance metrics.
- **DAG Initialization**: Automatically generates the root node for `hypothesis-dag.yaml`.

### Usage
```bash
python tools/sota_baseline.py --query "GNNs in drug discovery" --output baseline.yaml
```
