#!/usr/bin/env python3
"""
MIndex Vector Search — turbovec integration.

Adds state-of-the-art vector search to MIndex using Google's TurboQuant
algorithm (Rust, via turbovec). Complements the existing FTS5 keyword search.

Usage:
    python3 tools/mindex_vector.py build          # Build index from memory files
    python3 tools/mindex_vector.py search "..."   # Vector search
    python3 tools/mindex_vector.py hybrid "..."   # Vector + keyword combined
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import turbovec


# ---- Config ----
DEFAULT_INDEX_DIR = Path.home() / ".mindex"
DEFAULT_MEMORY_DIR = Path.cwd()
EMBEDDING_MODEL = "all-MiniLM-L6-v2"      # 384 dims, ~80MB
INDEX_FILENAME = "vector_index.tvim"
CHUNK_FILENAME = "vector_chunks.json"
DIM = 384


# ---- Lazy embedding model ----
_model = None

def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print(f"Loading embedding model ({EMBEDDING_MODEL})...", file=sys.stderr)
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


# ---- Chunk memory files ----
def find_memory_files(memory_dir: Path) -> list[Path]:
    """Find all markdown files to index."""
    files = []
    for ext in ("*.md", "*.mdx", "*.markdown"):
        files.extend(memory_dir.rglob(ext))
    # Skip non-content files
    skip = {"node_modules", ".git", "__pycache__", ".obsidian"}
    files = [f for f in files if not any(p in f.parts for p in skip)]
    # Skip index files
    files = [f for f in files if f.name.lower() not in
             ("index.md", "readme.md", "license.md", "contributing.md")]
    return sorted(files)


def chunk_markdown(text: str, max_chars: int = 1500, overlap: int = 200) -> list[str]:
    """Split markdown into overlapping chunks, trying to keep paragraphs intact."""
    # Split on double newlines (paragraphs)
    paragraphs = re.split(r'\n\n+', text.strip())
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para_len = len(para)

        if current_len + para_len > max_chars and current:
            chunks.append('\n\n'.join(current))
            # Keep last para for overlap
            overlap_text = current[-1] if current else ""
            current = [overlap_text] if overlap_text and len(overlap_text) < overlap * 2 else []
            current_len = sum(len(p) for p in current)

        current.append(para)
        current_len += para_len

    if current:
        chunks.append('\n\n'.join(current))
    return chunks


def build_chunks(memory_dir: Path, max_chars: int = 1500) -> list[dict]:
    """Build list of chunks with metadata."""
    files = find_memory_files(memory_dir)
    chunks = []
    chunk_id = 0

    for fpath in files:
        try:
            text = fpath.read_text(encoding="utf-8")
        except Exception:
            continue

        rel_path = str(fpath.relative_to(memory_dir))
        file_chunks = chunk_markdown(text, max_chars=max_chars)

        for c in file_chunks:
            chunks.append({
                "id": chunk_id,
                "path": rel_path,
                "text": c[:500],  # keep snippet in metadata
                "full_text": c,
            })
            chunk_id += 1

    return chunks


# ---- Vector index operations ----
def build_index(memory_dir: Path, index_dir: Path):
    """Build turbovec index from memory files."""
    print(f"Scanning {memory_dir}...", file=sys.stderr)
    chunks = build_chunks(memory_dir)
    print(f"Found {len(chunks)} chunks", file=sys.stderr)

    if not chunks:
        print("No content to index.", file=sys.stderr)
        return

    model = get_model()
    texts = [c["full_text"] for c in chunks]

    print(f"Generating embeddings ({len(texts)} texts)...", file=sys.stderr)
    t0 = time.time()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    t1 = time.time()
    print(f"Embedding done in {t1-t0:.1f}s ({len(texts)/(t1-t0):.0f} texts/s)", file=sys.stderr)

    # Build turbovec index
    index = turbovec.IdMapIndex(dim=DIM, bit_width=4)
    indices = np.arange(len(chunks), dtype=np.uint64)
    vectors_np = np.asarray(vectors, dtype=np.float32)

    index.add_with_ids(vectors_np, indices)
    index.prepare()

    # Save
    index_dir.mkdir(parents=True, exist_ok=True)
    index_path = index_dir / INDEX_FILENAME
    index.write(str(index_path))
    print(f"Index saved: {index_path}", file=sys.stderr)

    # Save chunk metadata
    chunk_path = index_dir / CHUNK_FILENAME
    # Strip full_text from saved metadata (keep snippets only)
    meta = [{"id": c["id"], "path": c["path"], "text": c["text"]} for c in chunks]
    chunk_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"Metadata saved: {chunk_path}", file=sys.stderr)
    print(f"Done. {len(chunks)} chunks indexed.", file=sys.stderr)


def load_index(index_dir: Path) -> tuple[Optional[turbovec.IdMapIndex], list[dict]]:
    """Load turbovec index and chunk metadata."""
    index_path = index_dir / INDEX_FILENAME
    chunk_path = index_dir / CHUNK_FILENAME

    if not index_path.exists() or not chunk_path.exists():
        print("No index found. Run 'build' first.", file=sys.stderr)
        return None, []

    index = turbovec.IdMapIndex.load(str(index_path))
    chunks = json.loads(chunk_path.read_text(encoding="utf-8"))
    return index, chunks


def search(index_dir: Path, query: str, k: int = 10):
    """Vector search using turbovec."""
    index, chunks = load_index(index_dir)
    if index is None:
        return []

    model = get_model()
    query_vec = model.encode(query, normalize_embeddings=True)
    query_np = np.expand_dims(np.asarray(query_vec, dtype=np.float32), axis=0)

    scores, ids = index.search(query_np, k=k)
    # scores is (1, k), ids is (1, k)
    results = []
    for score, cid in zip(scores[0], ids[0]):
        chunk = chunks[int(cid)]
        results.append({
            "id": int(cid),
            "path": chunk["path"],
            "text": chunk["text"],
            "score": float(score),
        })
    return results


# ---- CLI ----
def cmd_build(args):
    memory_dir = Path(args.memory_dir or DEFAULT_MEMORY_DIR)
    index_dir = Path(args.index_dir or DEFAULT_INDEX_DIR)
    build_index(memory_dir.resolve(), index_dir.resolve())


def cmd_search(args):
    index_dir = Path(args.index_dir or DEFAULT_INDEX_DIR)
    results = search(index_dir, args.query, k=args.k)
    for i, r in enumerate(results):
        print(f"{i+1}. [{r['score']:.3f}] {r['path']}")
        print(f"   {r['text'][:200]}")
        print()


def cmd_hybrid(args):
    """Hybrid search: vector + keyword (FTS5-like)."""
    # First do vector search
    index_dir = Path(args.index_dir or DEFAULT_INDEX_DIR)
    results = search(index_dir, args.query, k=args.k * 2)

    # Then re-rank with keyword overlap
    query_lower = args.query.lower()
    query_tokens = set(re.findall(r'\w+', query_lower))

    def keyword_score(text: str) -> float:
        text_lower = text.lower()
        tokens = set(re.findall(r'\w+', text_lower))
        if not query_tokens:
            return 0
        return len(query_tokens & tokens) / len(query_tokens)

    for r in results:
        r["keyword_score"] = keyword_score(r["text"])

    # Weighted combination
    vector_weight = 0.6
    keyword_weight = 0.4
    for r in results:
        r["combined"] = vector_weight * r["score"] + keyword_weight * r["keyword_score"]

    results.sort(key=lambda x: x["combined"], reverse=True)
    results = results[:args.k]

    for i, r in enumerate(results):
        print(f"{i+1}. [vec={r['score']:.3f}, kw={r['keyword_score']:.3f}] {r['path']}")
        print(f"   {r['text'][:200]}")
        print()


def build_arg_parser():
    parser = argparse.ArgumentParser(description="MIndex Vector Search")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Build vector index")
    p_build.add_argument("--index-dir", help="Index storage dir (default: ~/.mindex)")
    p_build.add_argument("--memory-dir", help="Memory files dir (default: cwd)")
    p_build.set_defaults(func=cmd_build)

    p_search = sub.add_parser("search", help="Vector search")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("-k", type=int, default=10, help="Number of results")
    p_search.add_argument("--index-dir", help="Index storage dir (default: ~/.mindex)")
    p_search.set_defaults(func=cmd_search)

    p_hybrid = sub.add_parser("hybrid", help="Hybrid vector+keyword search")
    p_hybrid.add_argument("query", help="Search query")
    p_hybrid.add_argument("-k", type=int, default=10, help="Number of results")
    p_hybrid.add_argument("--index-dir", help="Index storage dir (default: ~/.mindex)")
    p_hybrid.set_defaults(func=cmd_hybrid)

    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
