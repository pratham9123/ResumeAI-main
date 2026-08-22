"""Role-aware semantic retrieval over the persisted ResumeAI FAISS index."""

from __future__ import annotations

import copy
import functools
import re
import threading
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from modules.embedding_service import (
    DEFAULT_MODEL_NAME,
    sha256_text,
    Embedder,
    SentenceTransformerEmbeddingService,
    normalize_embeddings,
    validate_embedding_matrix,
)

from .indexing import (
    DEFAULT_INDEX_DIR,
    KnowledgeIndexBundle,
    KnowledgeIndexError,
    load_index_bundle,
)
from .schema import ALLOWED_ROLES, KnowledgeChunk


DEFAULT_TOP_K = 5
DEFAULT_MINIMUM_SIMILARITY = 0.25
OVERFETCH_MULTIPLIER = 5
MINIMUM_CANDIDATE_POOL = 20
NEAR_DUPLICATE_JACCARD = 0.90


class RetrievalError(RuntimeError):
    """Base class for retrieval failures."""


class RetrievalValidationError(RetrievalError, ValueError):
    """Raised when retrieval inputs are invalid."""


class RetrievalIndexError(RetrievalError):
    """Raised when the persisted index cannot be used for retrieval."""


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    id: str
    role: str
    category: str
    title: str
    text: str
    source: str
    tags: tuple[str, ...]
    similarity_score: float
    rank: int

    @classmethod
    def from_chunk(
        cls,
        chunk: KnowledgeChunk,
        *,
        similarity_score: float,
        rank: int,
    ) -> "RetrievalResult":
        return cls(
            id=chunk.id,
            role=chunk.role,
            category=chunk.category,
            title=chunk.title,
            text=chunk.text,
            source=chunk.source,
            tags=chunk.tags,
            similarity_score=round(float(similarity_score), 6),
            rank=rank,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        return payload


_index_load_lock = threading.RLock()


@functools.lru_cache(maxsize=8)
def _load_index_cached(resolved_index_dir: str, resolved_metadata_path: str) -> KnowledgeIndexBundle:
    """Load and validate one bundle per resolved path for the process lifetime."""
    return load_index_bundle(resolved_index_dir, metadata_path=resolved_metadata_path)


def _normalize_categories(categories: Sequence[str] | str | None) -> set[str] | None:
    if categories is None:
        return None
    values: Iterable[str] = [categories] if isinstance(categories, str) else categories
    normalized = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise RetrievalValidationError("categories must contain non-empty strings")
        normalized.add(value.strip().lower())
    return normalized


def _dedup_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#.-]+", text.lower()))


def _is_near_duplicate(text: str, accepted_token_sets: Sequence[set[str]]) -> bool:
    candidate = _dedup_tokens(text)
    if not candidate:
        return False
    for existing in accepted_token_sets:
        union = candidate | existing
        if not union:
            continue
        if len(candidate & existing) / len(union) >= NEAR_DUPLICATE_JACCARD:
            return True
    return False


class KnowledgeRetriever:
    """Search a loaded FAISS index and apply role-aware post-filtering."""

    def __init__(
        self,
        *,
        index_dir: str | Path = DEFAULT_INDEX_DIR,
        model_name: str = DEFAULT_MODEL_NAME,
        metadata_path: str | Path | None = None,
        embedder: Embedder | None = None,
        bundle: KnowledgeIndexBundle | None = None,
        cache_size: int = 128,
        cache_ttl_seconds: int = 300,
    ):
        try:
            resolved_index_dir = str(Path(index_dir).resolve())
            resolved_metadata = str(
                Path(metadata_path or Path(index_dir) / "chunks.json").resolve()
            )
            with _index_load_lock:
                self._bundle = bundle or _load_index_cached(
                    resolved_index_dir, resolved_metadata
                )
        except KnowledgeIndexError as exc:
            raise RetrievalIndexError(f"knowledge index is unavailable: {exc}") from exc

        indexed_model = self._bundle.config.get("model_name")
        if indexed_model != model_name:
            raise RetrievalIndexError(
                f"index model '{indexed_model}' is incompatible with requested model "
                f"'{model_name}'"
            )

        self._embedder = embedder or SentenceTransformerEmbeddingService(
            model_name=model_name
        )
        if self._embedder.model_name != indexed_model:
            raise RetrievalIndexError(
                f"query embedder model '{self._embedder.model_name}' does not match "
                f"index model '{indexed_model}'"
            )
        if cache_size < 0 or cache_ttl_seconds <= 0:
            raise ValueError("retrieval cache configuration is invalid")
        self._search_lock = threading.RLock()
        self._cache_lock = threading.RLock()
        self._cache_size = cache_size
        self._cache_ttl_seconds = cache_ttl_seconds
        self._result_cache: OrderedDict[str, tuple[float, list[dict[str, Any]]]] = OrderedDict()

    @property
    def chunk_count(self) -> int:
        return len(self._bundle.chunks)

    @property
    def knowledge_base_version(self) -> str:
        """Return the indexed corpus checksum used as its immutable version."""
        return str(self._bundle.config["knowledge_base_checksum"])

    def validate_ready(self) -> None:
        """Load the model and verify its output dimension against the FAISS index."""
        dimension = getattr(self._embedder, "dimension", None)
        if dimension is None:
            probe = validate_embedding_matrix(self._embedder.encode(["readiness"]), expected_count=1)
            dimension = int(probe.shape[1])
        expected = int(self._bundle.config["embedding_dimension"])
        if int(dimension) != expected:
            raise RetrievalIndexError(
                f"model dimension {dimension} does not match index dimension {expected}"
            )

    @staticmethod
    def _cache_key(query: str, role: str, categories: set[str] | None, top_k: int, threshold: float) -> str:
        category_key = ",".join(sorted(categories or set()))
        material = (
            f"{query.strip()}|{role}|{category_key}|{top_k}|{threshold:.6f}"
        )
        return sha256_text(material)


    def _cache_get(self, key: str) -> list[dict[str, Any]] | None:
        if self._cache_size == 0:
            return None
        with self._cache_lock:
            item = self._result_cache.get(key)
            if item is None:
                return None
            expires_at, results = item
            if expires_at <= time.monotonic():
                self._result_cache.pop(key, None)
                return None
            self._result_cache.move_to_end(key)
            return copy.deepcopy(results)
    def _cache_put(self, key: str, results: list[dict[str, Any]]) -> None:
        if self._cache_size == 0:
            return
        expires_at = time.monotonic() + self._cache_ttl_seconds
        with self._cache_lock:
            self._result_cache[key] = (expires_at, copy.deepcopy(results))
            self._result_cache.move_to_end(key)
            while len(self._result_cache) > self._cache_size:
                self._result_cache.popitem(last=False)

    def _search_candidates(self, query_vector: np.ndarray, count: int) -> list[tuple[int, float]]:
        try:
            with self._search_lock:
                scores, positions = self._bundle.index.search(query_vector, count)
        except Exception as exc:
            raise RetrievalIndexError(f"FAISS search failed: {exc}") from exc

        candidates = []
        for position, score in zip(positions[0], scores[0]):
            vector_position = int(position)
            if vector_position < 0:
                continue
            if vector_position >= len(self._bundle.chunks):
                raise RetrievalIndexError(
                    f"FAISS returned metadata position {vector_position}, but only "
                    f"{len(self._bundle.chunks)} chunks are loaded"
                )
            candidates.append((vector_position, float(score)))
        return candidates

    @staticmethod
    def _filter_candidates(
        candidates: Sequence[tuple[int, float]],
        chunks: Sequence[KnowledgeChunk],
        *,
        target_role: str,
        categories: set[str] | None,
        minimum_similarity: float,
        top_k: int,
    ) -> list[RetrievalResult]:
        allowed_roles = {target_role, "general"}
        accepted: list[tuple[KnowledgeChunk, float]] = []
        accepted_ids: set[str] = set()
        accepted_token_sets: list[set[str]] = []

        ordered = sorted(candidates, key=lambda item: (-item[1], item[0]))
        for position, score in ordered:
            chunk = chunks[position]
            if score < minimum_similarity:
                continue
            if chunk.role not in allowed_roles:
                continue
            if categories is not None and chunk.category not in categories:
                continue
            if chunk.id in accepted_ids:
                continue
            if _is_near_duplicate(chunk.text, accepted_token_sets):
                continue

            accepted.append((chunk, score))
            accepted_ids.add(chunk.id)
            accepted_token_sets.append(_dedup_tokens(chunk.text))
            if len(accepted) >= top_k:
                break

        return [
            RetrievalResult.from_chunk(chunk, similarity_score=score, rank=rank)
            for rank, (chunk, score) in enumerate(accepted, start=1)
        ]

    def retrieve(
        self,
        query: str,
        *,
        target_role: str,
        categories: Sequence[str] | str | None = None,
        top_k: int = DEFAULT_TOP_K,
        minimum_similarity: float = DEFAULT_MINIMUM_SIMILARITY,
    ) -> list[dict[str, Any]]:
        """Embed a concise query, search FAISS, filter, deduplicate, and rank."""
        if not isinstance(query, str) or not query.strip():
            raise RetrievalValidationError("retrieval query cannot be empty")

        normalized_role = str(target_role).strip().lower()
        if normalized_role not in ALLOWED_ROLES:
            allowed = ", ".join(sorted(ALLOWED_ROLES))
            raise RetrievalValidationError(
                f"unsupported target role '{normalized_role}'; expected one of: {allowed}"
            )
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
            raise RetrievalValidationError("top_k must be a positive integer")
        if not isinstance(minimum_similarity, (int, float)):
            raise RetrievalValidationError("minimum_similarity must be numeric")
        threshold = float(minimum_similarity)
        if not -1.0 <= threshold <= 1.0:
            raise RetrievalValidationError(
                "minimum_similarity must be between -1.0 and 1.0"
            )
        normalized_categories = _normalize_categories(categories)
        cache_key = self._cache_key(
            query, normalized_role, normalized_categories, top_k, threshold
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        try:
            raw_embedding = self._embedder.encode([query.strip()])
            validated = validate_embedding_matrix(raw_embedding, expected_count=1)
            query_vector = normalize_embeddings(validated)
        except RetrievalError:
            raise
        except Exception as exc:
            raise RetrievalError(f"query embedding failed: {exc}") from exc

        total = self._bundle.index.ntotal
        if total <= 0:
            return []
        candidate_count = min(
            total,
            max(top_k * OVERFETCH_MULTIPLIER, MINIMUM_CANDIDATE_POOL),
        )
        candidates = self._search_candidates(query_vector, candidate_count)
        results = self._filter_candidates(
            candidates,
            self._bundle.chunks,
            target_role=normalized_role,
            categories=normalized_categories,
            minimum_similarity=threshold,
            top_k=top_k,
        )

        # If filtering exhausted the initial pool, search the complete small index.
        if len(results) < top_k and candidate_count < total:
            candidates = self._search_candidates(query_vector, total)
            results = self._filter_candidates(
                candidates,
                self._bundle.chunks,
                target_role=normalized_role,
                categories=normalized_categories,
                minimum_similarity=threshold,
                top_k=top_k,
            )

        payload = [result.to_dict() for result in results]
        self._cache_put(cache_key, payload)
        return payload


@functools.lru_cache(maxsize=4)
def _get_cached_retriever(
    resolved_index_dir: str,
    model_name: str,
) -> KnowledgeRetriever:
    return KnowledgeRetriever(index_dir=resolved_index_dir, model_name=model_name)


def get_retriever(
    index_dir: str | Path = DEFAULT_INDEX_DIR,
    model_name: str = DEFAULT_MODEL_NAME,
) -> KnowledgeRetriever:
    """Return a process-cached production retriever."""
    return _get_cached_retriever(str(Path(index_dir).resolve()), model_name)
