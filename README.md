# Original Dissent Archivist

A PN Desktop plugin for browsing and searching the Original Dissent forum archive (2001-2005).

## Overview

- **108,898 posts** across **16,591 threads** from **916 users**
- Semantic full-text search via [KitsapSearchEngine](https://github.com/promptneurons/KitsapSearchEngine)
- SPARQL metadata queries via local Virtuoso
- Markdown rendering via local viewer
- Zero cloud dependencies

## Architecture

```
User query
    │
    ▼
scripts/search.py          ← semantic ranking layer
    ├── CEC classifier      (Cutter Expansive Classification, zero-shot)
    ├── SUMO expansion      (WordNet 3.0 → SUMO concepts, bridges vocabulary)
    └── od-cache.jsonl      (precomputed per-thread vectors, ~10MB)
    │
    ▼
Ranked thread IDs + scores
    │
    ├── scripts/get-thread.py  ← content retrieval
    │       └── SQLite (~420MB)  posts_markdown.db
    │
    └── Virtuoso (optional)    ← metadata / SPARQL discovery
            └── od-2006-threads-full.ttl
                od-2006-users.ttl
```

**KitsapSearchEngine** is the semantic layer:
- CEC (Cutter Expansive Classification) — universal subject classification
- SUMO/WordNet — ontological concept expansion (bridges informal ↔ formal vocabulary)
- `external_sumo` profile: `CEC=0.50 · Keywords=0.20 · SUMO=0.30`

## Installation

### 1. Install PN Desktop
```bash
# Coming soon
```

### 2. Download the archive DLC
```bash
# SQLite database (~420MB)
curl -O https://s3.amazonaws.com/kitsap/dlc/od-2006/posts_markdown.db
mv posts_markdown.db ~/.pn-desktop/plugins/od-archivist/data/
```

### 3. Clone KitsapSearchEngine and build the search index
```bash
git clone https://github.com/promptneurons/KitsapSearchEngine
cd KitsapSearchEngine

# Extract threads (requires od-2006/posts_markdown.db)
python3 scripts/od-extract-threads.py

# Build semantic cache (with SUMO — recommended)
python3 scripts/gln-precompute.py \
  --index data/od-thread-index.yaml \
  --output data/od-cache.jsonl

# Test search
python3 scripts/gln-ranker.py \
  --cache data/od-cache.jsonl \
  --profile external_sumo \
  --pool 200 --top 10
```

### 4. Load metadata into Virtuoso (optional)
```bash
curl -T ttl/od-2006-threads-full.ttl http://localhost:8890/DAV/home/dba/rdf_sink/
curl -T ttl/od-2006-users.ttl        http://localhost:8890/DAV/home/dba/rdf_sink/
```

## Usage

### Semantic search
```bash
# Search by topic (uses CEC + SUMO)
python3 scripts/search.py "paleoconservatism Buchanan foreign policy"
python3 scripts/search.py "Byzantine schism church music" --top 5
python3 scripts/search.py "the Enlightenment reason tradition" --no-sumo

# Point to custom cache
python3 scripts/search.py "query" --cache /path/to/od-cache.jsonl
```

### View a thread
```bash
python3 scripts/get-thread.py 15678
python3 scripts/get-thread.py 15678 --post-to-hastebin
```

### View user activity
```bash
python3 scripts/get-user.py --name "il ragno"
python3 scripts/get-user.py 85
```

## Data Sources

| Source | Description | Size |
|--------|-------------|------|
| SQLite | Full post content, markdown-rendered | ~420MB DLC |
| od-cache.jsonl | Precomputed semantic vectors (KitsapSearchEngine) | ~10MB |
| Virtuoso | Thread/user metadata, SPARQL queries | optional |
| Wayback | Visual snapshots linked, not stored | — |

## Semantic Search Design

The search pipeline is built around three axes:

1. **CEC (Cutter Expansive Classification)** — classifies threads to universal library subject classes (A=Philosophy, B=Theology, C=History, F=Society, H=Politics…). Zero-shot: no training data required.

2. **Keyword Jaccard** — surface token overlap between query and thread OP. Fast, precise for exact terms.

3. **SUMO semantic expansion** — maps keywords to SUMO ontology concepts via WordNet 3.0. Bridges vocabulary differences: "troops" and "military" both resolve to `MilitaryForce`; "priest" and "clergy" both resolve to `Cleric`. Works across 147k lemmas / 112k synsets.

**Why this matters for OD-2006:** the forum uses colloquial, period-specific vocabulary. CEC + SUMO lets you search for concepts rather than exact words, without any training data or cloud dependencies.

## Subject Distribution (CEC)

From the full 10,561-thread index:

| CEC | Subject | Threads | % |
|-----|---------|---------|---|
| F | Social Sciences / Society | 2,176 | 20.6% |
| H | History | 1,055 | 10.0% |
| E | Natural Sciences | 1,046 | 9.9% |
| C | General History | 1,035 | 9.8% |
| (unclassified) | — | 972 | 9.2% |

## License

Content: Original Dissent forum archive (fair use / preservation)  
Code: MIT

## Links

- [KitsapSearchEngine](https://github.com/promptneurons/KitsapSearchEngine) — semantic search layer
- [PN Desktop](https://github.com/promptneurons/pn-desktop) — host application
- [Wayback: Original Dissent](https://web.archive.org/web/2006/http://www.originaldissent.com/)
