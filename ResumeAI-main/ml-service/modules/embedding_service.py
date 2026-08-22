"""Shared SentenceTransformer embedding service for scoring and RAG indexing."""

from __future__ import annotations

import functools
import hashlib
import logging
import threading
from typing import Protocol, Sequence

import numpy as np


logger = logging.getLogger(__name__)
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


class EmbeddingError(RuntimeError):
    """Raised when an embedding model returns unusable output."""


class Embedder(Protocol):
    """Minimal interface accepted by the index builder."""

    model_name: str

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Encode texts into a two-dimensional float32 array."""


def sha256_text(text: str) -> str:
    """Return a stable SHA-256 digest for UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


_model_load_lock = threading.RLock()


@functools.lru_cache(maxsize=2)
def _load_sentence_transformer(model_name: str):
    """Load at most one SentenceTransformer instance for each model name."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingError(
            "sentence-transformers is not installed; install ml-service requirements"
        ) from exc

    logger.info("Loading shared sentence transformer model (%s)...", model_name)
    model = SentenceTransformer(model_name)
    logger.info("Shared sentence transformer model loaded (%s).", model_name)
    return model

def get_shared_sentence_transformer(model_name: str = DEFAULT_MODEL_NAME):
    """Return one model instance per name, including during concurrent startup."""
    with _model_load_lock:
        return _load_sentence_transformer(model_name)



def validate_embedding_matrix(
    embeddings: np.ndarray,
    *,
    expected_count: int,
) -> np.ndarray:
    """Validate model output and return a contiguous float32 matrix."""
    matrix = np.asarray(embeddings, dtype=np.float32)
    if matrix.ndim != 2:
        raise EmbeddingError(
            f"embedding output must be two-dimensional; got shape {matrix.shape}"
        )
    if matrix.shape[0] != expected_count:
        raise EmbeddingError(
            f"embedding row count {matrix.shape[0]} does not match input count {expected_count}"
        )
    if matrix.shape[1] <= 0:
        raise EmbeddingError("embedding dimension must be greater than zero")
    if not np.isfinite(matrix).all():
        raise EmbeddingError("embedding output contains NaN or infinite values")
    if np.any(np.linalg.norm(matrix, axis=1) == 0):
        raise EmbeddingError("embedding output contains a zero-length vector")
    return np.ascontiguousarray(matrix, dtype=np.float32)


def normalize_embeddings(embeddings: np.ndarray) -> np.ndarray:
    """L2-normalize rows so inner product is equivalent to cosine similarity."""
    matrix = np.asarray(embeddings, dtype=np.float32)
    if matrix.ndim != 2:
        raise EmbeddingError("only two-dimensional embedding matrices can be normalized")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0) or not np.isfinite(norms).all():
        raise EmbeddingError("cannot normalize zero-length or non-finite embeddings")
    return np.ascontiguousarray(matrix / norms, dtype=np.float32)


class SentenceTransformerEmbeddingService:
    """Batch embedding adapter backed by the process-wide shared model cache."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME, batch_size: int = 32):
        if not model_name.strip():
            raise ValueError("model_name cannot be empty")
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        self.model_name = model_name.strip()
        self.batch_size = batch_size

    @property
    def model(self):
        return get_shared_sentence_transformer(self.model_name)

    @property
    def dimension(self) -> int:
        getter = getattr(self.model, "get_sentence_embedding_dimension", None)
        if callable(getter):
            dimension = getter()
            if isinstance(dimension, int) and dimension > 0:
                return dimension
        return int(self.encode(["ResumeAI model readiness check"]).shape[1])

    def encode(self, texts: Sequence[str]) -> np.ndarray:

        normalized_inputs = [str(text).strip() for text in texts]
        if not normalized_inputs:
            raise EmbeddingError("cannot generate embeddings for an empty text collection")
        if any(not text for text in normalized_inputs):
            raise EmbeddingError("embedding input contains empty text")

        output = self.model.encode(
            normalized_inputs,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=False,
            show_progress_bar=False,
        )
        return validate_embedding_matrix(output, expected_count=len(normalized_inputs))


@functools.lru_cache(maxsize=64)
def cached_encode_text(
    text_hash: str,
    text: str,
    model_name: str = DEFAULT_MODEL_NAME,
) -> np.ndarray:
    """Encode one text using the existing bounded SHA-256 keyed memory cache."""
    if sha256_text(text) != text_hash:
        raise EmbeddingError("text_hash does not match embedding input")
    service = SentenceTransformerEmbeddingService(model_name=model_name)
    return service.encode([text])[0]
