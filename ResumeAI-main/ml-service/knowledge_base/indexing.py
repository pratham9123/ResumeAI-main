"""Embedding generation and persisted FAISS index creation for knowledge chunks."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from modules.embedding_service import (
    DEFAULT_MODEL_NAME,
    Embedder,
    SentenceTransformerEmbeddingService,
    normalize_embeddings,
    sha256_text,
    validate_embedding_matrix,
)

from .loader import DEFAULT_DATA_DIR, load_knowledge_base
from .schema import KnowledgeChunk, KnowledgeValidationError


INDEX_FORMAT_VERSION = 1
INDEX_TYPE = "IndexFlatIP"
DISTANCE_METRIC = "inner_product"
EMBEDDING_TEXT_FORMAT = "role_category_title_text_v1"
DEFAULT_INDEX_DIR = Path(__file__).resolve().parent / "index"
INDEX_FILENAME = "knowledge.faiss"
CHUNKS_FILENAME = "chunks.json"
CONFIG_FILENAME = "index_config.json"


class KnowledgeIndexError(RuntimeError):
    """Base class for knowledge-index build and load failures."""


class EmptyKnowledgeBaseError(KnowledgeIndexError):
    """Raised when no validated knowledge chunks are available."""


class MissingIndexMetadataError(KnowledgeIndexError):
    """Raised when one or more persisted index artifacts are missing."""


class CorruptIndexError(KnowledgeIndexError):
    """Raised when a persisted FAISS or JSON artifact cannot be read."""


class IncompatibleIndexError(KnowledgeIndexError):
    """Raised when persisted artifacts disagree about their configuration."""


@dataclass(frozen=True, slots=True)
class IndexPaths:
    root: Path
    index: Path
    chunks: Path
    config: Path

    @classmethod
    def from_root(cls, root: str | Path) -> "IndexPaths":
        directory = Path(root)
        return cls(
            root=directory,
            index=directory / INDEX_FILENAME,
            chunks=directory / CHUNKS_FILENAME,
            config=directory / CONFIG_FILENAME,
        )


@dataclass(slots=True)
class KnowledgeIndexBundle:
    """Validated persisted index plus vector-aligned metadata."""

    index: Any
    chunks: list[KnowledgeChunk]
    config: dict[str, Any]
    paths: IndexPaths


@dataclass(slots=True)
class IndexBuildResult:
    """Outcome of ensuring that a compatible index exists."""

    action: str
    reason: str
    bundle: KnowledgeIndexBundle

    @property
    def rebuilt(self) -> bool:
        return self.action == "rebuilt"


def _import_faiss():
    try:
        import faiss
    except ImportError as exc:
        raise KnowledgeIndexError(
            "faiss-cpu is not installed; install ml-service requirements"
        ) from exc
    return faiss


def _chunk_to_embedding_text(chunk: KnowledgeChunk) -> str:
    return (
        f"Role: {chunk.role}\n"
        f"Category: {chunk.category}\n"
        f"Title: {chunk.title}\n"
        f"Guidance: {chunk.text}"
    )


def compute_knowledge_checksum(chunks: Sequence[KnowledgeChunk]) -> str:
    """Hash normalized chunks in vector order using canonical JSON."""
    canonical = json.dumps(
        [chunk.to_dict() for chunk in chunks],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_text(canonical)


def _load_validated_chunks(data_dir: str | Path | None) -> list[KnowledgeChunk]:
    result = load_knowledge_base(data_dir or DEFAULT_DATA_DIR)
    if result.issues:
        details = "\n".join(str(issue) for issue in result.issues)
        raise KnowledgeIndexError(
            f"knowledge base validation reported {len(result.issues)} issue(s):\n{details}"
        )
    if not result.chunks:
        raise EmptyKnowledgeBaseError("cannot build an index from an empty knowledge base")
    return result.chunks


def _read_json(path: Path, label: str) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise MissingIndexMetadataError(f"missing {label}: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CorruptIndexError(f"could not read {label} '{path}': {exc}") from exc


def _validate_config(config: Any) -> dict[str, Any]:
    required = {
        "format_version",
        "index_type",
        "metric",
        "model_name",
        "embedding_dimension",
        "chunk_count",
        "knowledge_base_checksum",
        "embedding_text_format",
        "created_at",
    }
    if not isinstance(config, dict):
        raise IncompatibleIndexError("index configuration must be a JSON object")
    missing = sorted(required - config.keys())
    if missing:
        raise IncompatibleIndexError(
            f"index configuration is missing: {', '.join(missing)}"
        )
    if config["format_version"] != INDEX_FORMAT_VERSION:
        raise IncompatibleIndexError(
            f"unsupported index format version {config['format_version']}"
        )
    if config["index_type"] != INDEX_TYPE or config["metric"] != DISTANCE_METRIC:
        raise IncompatibleIndexError("persisted index type or metric is incompatible")
    if config["embedding_text_format"] != EMBEDDING_TEXT_FORMAT:
        raise IncompatibleIndexError("embedding text format has changed")
    if not isinstance(config["embedding_dimension"], int) or config["embedding_dimension"] <= 0:
        raise IncompatibleIndexError("embedding dimension must be a positive integer")
    if not isinstance(config["chunk_count"], int) or config["chunk_count"] < 0:
        raise IncompatibleIndexError("chunk count must be a non-negative integer")
    if not isinstance(config["model_name"], str) or not config["model_name"].strip():
        raise IncompatibleIndexError("model name is missing from index configuration")
    return config


def load_index_bundle(
    index_dir: str | Path = DEFAULT_INDEX_DIR,
    *,
    metadata_path: str | Path | None = None,
) -> KnowledgeIndexBundle:
    """Load persisted artifacts and verify counts, dimensions, metric, and checksum."""
    faiss = _import_faiss()
    paths = IndexPaths.from_root(index_dir)
    if metadata_path is not None:
        paths = IndexPaths(
            root=paths.root,
            index=paths.index,
            chunks=Path(metadata_path),
            config=paths.config,
        )

    config = _validate_config(_read_json(paths.config, "index configuration"))
    metadata = _read_json(paths.chunks, "chunk metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("chunks"), list):
        raise IncompatibleIndexError("chunk metadata must contain a 'chunks' array")

    chunks: list[KnowledgeChunk] = []
    seen_ids: set[str] = set()
    for position, payload in enumerate(metadata["chunks"]):
        try:
            chunk = KnowledgeChunk.from_dict(payload)
        except KnowledgeValidationError as exc:
            raise IncompatibleIndexError(
                f"invalid chunk metadata at vector position {position}: {exc}"
            ) from exc
        if chunk.id in seen_ids:
            raise IncompatibleIndexError(f"duplicate chunk id in metadata: {chunk.id}")
        seen_ids.add(chunk.id)
        chunks.append(chunk)

    if len(chunks) != config["chunk_count"]:
        raise IncompatibleIndexError(
            "chunk metadata count does not match index configuration"
        )
    if compute_knowledge_checksum(chunks) != config["knowledge_base_checksum"]:
        raise IncompatibleIndexError("chunk metadata checksum does not match configuration")

    if not paths.index.exists():
        raise MissingIndexMetadataError(f"missing FAISS index: {paths.index}")
    try:
        index = faiss.read_index(str(paths.index))
    except Exception as exc:
        raise CorruptIndexError(f"could not read FAISS index '{paths.index}': {exc}") from exc

    if index.d != config["embedding_dimension"]:
        raise IncompatibleIndexError(
            f"FAISS dimension {index.d} does not match configured dimension "
            f"{config['embedding_dimension']}"
        )
    if index.ntotal != config["chunk_count"]:
        raise IncompatibleIndexError(
            f"FAISS vector count {index.ntotal} does not match chunk count "
            f"{config['chunk_count']}"
        )
    if getattr(index, "metric_type", None) != faiss.METRIC_INNER_PRODUCT:
        raise IncompatibleIndexError("FAISS index does not use inner-product distance")

    return KnowledgeIndexBundle(index=index, chunks=chunks, config=config, paths=paths)


def _write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _persist_index(
    index: Any,
    chunks: Sequence[KnowledgeChunk],
    config: dict[str, Any],
    paths: IndexPaths,
) -> None:
    faiss = _import_faiss()
    paths.root.mkdir(parents=True, exist_ok=True)
    temporary = IndexPaths(
        root=paths.root,
        index=paths.index.with_suffix(paths.index.suffix + ".tmp"),
        chunks=paths.chunks.with_suffix(paths.chunks.suffix + ".tmp"),
        config=paths.config.with_suffix(paths.config.suffix + ".tmp"),
    )
    try:
        faiss.write_index(index, str(temporary.index))
        _write_json(temporary.chunks, {"chunks": [chunk.to_dict() for chunk in chunks]})
        _write_json(temporary.config, config)

        os.replace(temporary.index, paths.index)
        os.replace(temporary.chunks, paths.chunks)
        os.replace(temporary.config, paths.config)
    except Exception as exc:
        raise KnowledgeIndexError(f"failed to persist knowledge index: {exc}") from exc
    finally:
        for path in (temporary.index, temporary.chunks, temporary.config):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def _build_index(
    chunks: Sequence[KnowledgeChunk],
    embedder: Embedder,
    checksum: str,
    paths: IndexPaths,
) -> KnowledgeIndexBundle:
    faiss = _import_faiss()
    texts = [_chunk_to_embedding_text(chunk) for chunk in chunks]
    raw = embedder.encode(texts)
    validated = validate_embedding_matrix(raw, expected_count=len(chunks))
    embeddings = normalize_embeddings(validated)

    dimension = int(embeddings.shape[1])
    index = faiss.IndexFlatIP(dimension)
    if index.d != dimension:
        raise IncompatibleIndexError(
            f"created FAISS dimension {index.d} does not match embeddings {dimension}"
        )
    try:
        index.add(embeddings)
    except Exception as exc:
        raise IncompatibleIndexError(
            f"FAISS rejected {len(embeddings)} embeddings with dimension {dimension}: {exc}"
        ) from exc
    if index.ntotal != len(chunks):
        raise IncompatibleIndexError("FAISS did not store the expected number of vectors")

    config = {
        "format_version": INDEX_FORMAT_VERSION,
        "index_type": INDEX_TYPE,
        "metric": DISTANCE_METRIC,
        "model_name": embedder.model_name,
        "embedding_dimension": dimension,
        "chunk_count": len(chunks),
        "knowledge_base_checksum": checksum,
        "embedding_text_format": EMBEDDING_TEXT_FORMAT,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _persist_index(index, chunks, config, paths)
    return load_index_bundle(paths.root)


def ensure_knowledge_index(
    *,
    data_dir: str | Path | None = None,
    index_dir: str | Path = DEFAULT_INDEX_DIR,
    model_name: str = DEFAULT_MODEL_NAME,
    embedder: Embedder | None = None,
    force: bool = False,
) -> IndexBuildResult:
    """Reuse a compatible index or rebuild it for a precise recorded reason."""
    chunks = _load_validated_chunks(data_dir)
    checksum = compute_knowledge_checksum(chunks)
    active_embedder = embedder or SentenceTransformerEmbeddingService(model_name=model_name)
    if active_embedder.model_name != model_name:
        raise KnowledgeIndexError(
            f"embedder model '{active_embedder.model_name}' does not match requested model "
            f"'{model_name}'"
        )
    paths = IndexPaths.from_root(index_dir)

    rebuild_reason: str | None = "forced rebuild" if force else None
    existing: KnowledgeIndexBundle | None = None
    if rebuild_reason is None:
        try:
            existing = load_index_bundle(paths.root)
        except MissingIndexMetadataError as exc:
            rebuild_reason = str(exc)
        except (CorruptIndexError, IncompatibleIndexError) as exc:
            rebuild_reason = str(exc)

    if existing is not None:
        config = existing.config
        if config["model_name"] != model_name:
            rebuild_reason = (
                f"model changed from '{config['model_name']}' to '{model_name}'"
            )
        elif config["knowledge_base_checksum"] != checksum:
            rebuild_reason = "knowledge-base checksum changed"
        elif config["chunk_count"] != len(chunks):
            rebuild_reason = "knowledge-base chunk count changed"
        else:
            return IndexBuildResult(
                action="reused",
                reason="stored index is compatible and knowledge is unchanged",
                bundle=existing,
            )

    bundle = _build_index(chunks, active_embedder, checksum, paths)
    return IndexBuildResult(
        action="rebuilt",
        reason=rebuild_reason or "index was not reusable",
        bundle=bundle,
    )
