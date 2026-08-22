"""Deployment hook that creates or validates RAG artifacts before Flask starts."""

from __future__ import annotations

from knowledge_base.indexing import KnowledgeIndexError, ensure_knowledge_index
from modules.rag_runtime import RAGConfigurationError, RAGSettings


def main() -> int:
    try:
        settings = RAGSettings.from_env()
    except RAGConfigurationError as exc:
        print(f"RAG configuration invalid: {type(exc).__name__}")
        return 1

    if not settings.enabled:
        print("RAG preparation skipped: disabled")
        return 0

    try:
        result = ensure_knowledge_index(
            index_dir=settings.index_path,
            model_name=settings.model_name,
        )
    except KnowledgeIndexError as exc:
        print(f"RAG preparation failed: {type(exc).__name__}")
        return 1

    expected_metadata = result.bundle.paths.chunks.resolve()
    if settings.metadata_path.resolve() != expected_metadata:
        print("RAG preparation failed: configured metadata path does not match build output")
        return 1

    config = result.bundle.config
    print(
        "RAG preparation complete: "
        f"action={result.action} vectors={config['chunk_count']} "
        f"dimension={config['embedding_dimension']} "
        f"version={config['knowledge_base_checksum']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
