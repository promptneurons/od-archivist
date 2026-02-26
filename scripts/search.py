#!/usr/bin/env python3
"""
search.py - Semantic search over the Original Dissent archive

Uses KitsapSearchEngine (CEC + SUMO) for relevance ranking, SQLite
for content retrieval.  Zero cloud dependencies.

Usage:
  python3 scripts/search.py "Byzantine schism church music"
  python3 scripts/search.py "paleoconservatism Buchanan" --top 10
  python3 scripts/search.py "the Enlightenment" --cache /path/to/od-cache.jsonl

Environment:
  KSE_PATH   Path to KitsapSearchEngine repo root (default: ../KitsapSearchEngine)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# KitsapSearchEngine path resolution
# ─────────────────────────────────────────────────────────────────────────────

def _find_kse(hint=None):
    candidates = []
    if hint:
        candidates.append(Path(hint))
    env = os.environ.get("KSE_PATH")
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve().parent.parent
    candidates += [
        here.parent / "KitsapSearchEngine",
        Path.home() / "KitsapSearchEngine",
        Path("/home/john/KitsapSearchEngine"),
    ]
    for p in candidates:
        if (p / "scripts" / "gln-ranker.py").exists():
            return p
    return None


def _load_module(path, name):
    import importlib.util as _ilu
    sp = _ilu.spec_from_file_location(name, path)
    mod = _ilu.module_from_spec(sp)
    sp.loader.exec_module(mod)
    return mod


# ─────────────────────────────────────────────────────────────────────────────
# Minimal inline CEC classifier (no N200 index needed)
# ─────────────────────────────────────────────────────────────────────────────

# Keyword → CEC class heuristic (same logic as gln-resolver CEC axis)
_CEC_KEYWORDS = {
    "A": ["philosophy", "metaphysics", "logic", "aesthetics", "epistemology", "ethics"],
    "B": ["theology", "religion", "christianity", "church", "bible", "scripture",
          "catholicism", "protestant", "orthodox", "islam", "jewish", "judaism",
          "byzantine", "liturgy", "canon", "doctrine"],
    "C": ["history", "ancient", "medieval", "classical", "rome", "greece",
          "renaissance", "reformation", "empire", "civilization", "dynasty"],
    "D": ["language", "linguistics", "grammar", "latin", "greek", "german",
          "french", "literature", "poetry", "prose", "rhetoric"],
    "E": ["science", "biology", "chemistry", "physics", "mathematics",
          "evolution", "genetics", "ecology", "astronomy", "geology"],
    "F": ["society", "sociology", "culture", "race", "ethnicity", "family",
          "demographics", "immigration", "population", "community", "identity"],
    "H": ["politics", "government", "democracy", "republic", "state",
          "nationalism", "conservatism", "liberalism", "fascism", "communism",
          "election", "policy", "war", "military", "foreign", "geopolitics"],
    "J": ["economics", "trade", "capitalism", "market", "finance", "banking",
          "monetary", "currency", "inflation", "debt", "globalism"],
    "K": ["law", "legal", "legislation", "constitution", "rights", "justice",
          "court", "crime", "punishment", "freedom"],
    "L": ["art", "music", "painting", "architecture", "film", "cinema",
          "theater", "aesthetics", "visual", "cultural"],
    "M": ["education", "university", "school", "learning", "academic",
          "curriculum", "pedagogy", "scholarship", "intellectual"],
    "N": ["technology", "computer", "internet", "software", "digital",
          "media", "journalism", "press", "propaganda", "censorship"],
}

_STOPWORDS = set("""
a an the and or but in on at to of for with by from as is was are were be been
being have has had do does did will would could should may might shall can its
it this that these those i me my we our you your he she his her they them their
not no nor so if then when where what who how all any each some such only just
also very more most over about up out into after before while during between
""".split())


def classify_cec(text):
    """Simple keyword-frequency CEC classifier. Returns (class, score)."""
    words = re.findall(r"[a-z]{3,}", text.lower())
    words = [w for w in words if w not in _STOPWORDS]
    scores = {k: 0 for k in _CEC_KEYWORDS}
    for word in words:
        for cls, kws in _CEC_KEYWORDS.items():
            if word in kws:
                scores[cls] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None, scores[best]


def extract_keywords(text, top_n=20):
    words = re.findall(r"[a-z]{3,}", text.lower())
    freq = {}
    for w in words:
        if w not in _STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:top_n]]


# ─────────────────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────────────────

def _jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def score_entry(query_cec, query_kw, query_sumo, entry, W):
    """Score a cache entry against the query vectors."""
    r_cec = 0.0
    if query_cec and entry.get("cec"):
        if query_cec == entry["cec"]:
            r_cec = 1.0
        elif query_cec[0] == entry["cec"][0]:
            r_cec = 0.3

    r_kw   = _jaccard(query_kw,   entry.get("keywords", []))
    r_sumo = _jaccard(query_sumo, entry.get("sumo_concepts", []))

    return W["cec"] * r_cec + W["kw"] * r_kw + W["sumo"] * r_sumo


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Semantic search over Original Dissent archive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("query", nargs="?", help="Search query text")
    parser.add_argument("--top", "-t", type=int, default=10, help="Results to show (default 10)")
    parser.add_argument("--cache", "-c", help="Path to od-cache.jsonl")
    parser.add_argument("--kse-path", help="Path to KitsapSearchEngine repo root")
    parser.add_argument("--no-sumo", action="store_true", help="Disable SUMO expansion")
    parser.add_argument("--cec-weight",  type=float, default=0.50)
    parser.add_argument("--kw-weight",   type=float, default=0.20)
    parser.add_argument("--sumo-weight", type=float, default=0.30)
    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        sys.exit(0)

    query = args.query
    W = {"cec": args.cec_weight, "kw": args.kw_weight,
         "sumo": 0.0 if args.no_sumo else args.sumo_weight}

    # Locate KitsapSearchEngine
    kse = _find_kse(args.kse_path)
    if not kse:
        print("ERROR: KitsapSearchEngine not found. Set KSE_PATH or use --kse-path.", file=sys.stderr)
        sys.exit(1)

    # Locate cache
    cache_path = Path(args.cache) if args.cache else kse / "data" / "od-cache.jsonl"
    if not cache_path.exists():
        print(f"ERROR: Cache not found: {cache_path}", file=sys.stderr)
        print("Run: python3 scripts/gln-precompute.py --index data/od-thread-index.yaml "
              "--output data/od-cache.jsonl", file=sys.stderr)
        sys.exit(1)

    # Classify query
    query_cec, _ = classify_cec(query)
    query_kw     = extract_keywords(query)

    # SUMO expansion
    query_sumo = []
    if W["sumo"] > 0:
        try:
            sw = _load_module(kse / "scripts" / "sumo_wordnet.py", "sumo_wordnet")
            wn_path = kse / "data" / "wordnet-mappings"
            if wn_path.exists():
                idx, maps = sw.load_sumo_db(wn_path)
                query_sumo = list(sw.words_to_sumo(query_kw, idx, maps))
            else:
                print(f"WARN: WordNet not found at {wn_path}, SUMO disabled", file=sys.stderr)
                W["sumo"] = 0.0
        except Exception as e:
            print(f"WARN: SUMO load failed ({e}), falling back to CEC+keywords", file=sys.stderr)
            W["sumo"] = 0.0

    # Renormalise weights
    total = sum(W.values())
    if total > 0:
        W = {k: v / total for k, v in W.items()}

    print(f"Query:    {query!r}", file=sys.stderr)
    print(f"CEC:      {query_cec or '(none)'}", file=sys.stderr)
    print(f"Keywords: {query_kw[:8]}", file=sys.stderr)
    print(f"SUMO:     {sorted(query_sumo)[:6]}", file=sys.stderr)
    print(f"Weights:  cec={W['cec']:.2f} kw={W['kw']:.2f} sumo={W['sumo']:.2f}", file=sys.stderr)
    print(f"Cache:    {cache_path} ({cache_path.stat().st_size // 1024}K)", file=sys.stderr)
    print("", file=sys.stderr)

    # Load cache + score
    scored = []
    with open(cache_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            s = score_entry(query_cec, query_kw, query_sumo, entry, W)
            if s > 0:
                scored.append((s, entry))

    scored.sort(key=lambda x: -x[0])
    results = scored[:args.top]

    if not results:
        print("No results found.")
        return

    # Render SERP
    print(f"# Search: {query}")
    print(f"*{len(scored)} matches · showing top {len(results)}*")
    print()
    for rank, (score, entry) in enumerate(results, 1):
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        tid = Path(entry["path"]).stem.replace("thread-", "")
        print(f"### {rank}. {entry['title']}")
        print(f"`{bar}` **{score:.3f}**  ·  thread `{tid}`  ·  CEC:{entry.get('cec','?')}")
        if entry.get("snippet"):
            import html as _h
            snip = _h.unescape(entry["snippet"])
            if snip.startswith(("threadid:", "title:", "source:")):
                # Parse YAML op field
                try:
                    import yaml as _y
                    doc = _y.safe_load(snip)
                    snip = str(doc.get("op", ""))[:200]
                except Exception:
                    pass
            print(f"> {snip[:200]}")
        sumo_hits = set(query_sumo) & set(entry.get("sumo_concepts", []))
        if sumo_hits:
            print(f"*SUMO bridge: {', '.join(sorted(sumo_hits)[:4])}*")
        print()


if __name__ == "__main__":
    main()
