"""CLI for building or validating the persisted ResumeAI FAISS index."""

from __future__ import annotations

import argparse
from pathlib import Path

from modules.embedding_service import DEFAULT_MODEL_NAME

from .indexing import DEFAULT_INDEX_DIR, KnowledgeIndexError, ensure_knowledge_index
from .loader import DEFAULT_DATA_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the ResumeAI knowledge FAISS index")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--force", action="store_true", help="rebuild even if compatible")
    args = parser.parse_args()

    try:
        result = ensure_knowledge_index(
            data_dir=args.data_dir,
            index_dir=args.index_dir,
            model_name=args.model,
            force=args.force,
        )
    except KnowledgeIndexError as exc:
        print(f"Index build failed: {exc}")
        return 1

    config = result.bundle.config
    print(f"Index action: {result.action}")
    print(f"Reason: {result.reason}")
    print(
        f"Vectors: {config['chunk_count']} | Dimension: {config['embedding_dimension']} | "
        f"Model: {config['model_name']}"
    )
    print(f"Knowledge checksum: {config['knowledge_base_checksum']}")
    print(f"FAISS index: {result.bundle.paths.index}")
    print(f"Chunk metadata: {result.bundle.paths.chunks}")
    print(f"Index configuration: {result.bundle.paths.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
