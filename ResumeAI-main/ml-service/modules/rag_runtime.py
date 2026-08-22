"""Validated, process-wide runtime state for optional RAG retrieval."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from knowledge_base.indexing import CHUNKS_FILENAME, DEFAULT_INDEX_DIR
from knowledge_base.retriever import KnowledgeRetriever, RetrievalError
from modules.embedding_service import DEFAULT_MODEL_NAME


logger = logging.getLogger(__name__)


class RAGConfigurationError(ValueError):
    """Raised when RAG environment configuration is invalid."""


def _flag(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RAGConfigurationError("boolean configuration value is invalid")


def _integer(env: Mapping[str, str], name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(env.get(name, str(default)))
    except ValueError as exc:
        raise RAGConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise RAGConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


def _floating(env: Mapping[str, str], name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(env.get(name, str(default)))
    except ValueError as exc:
        raise RAGConfigurationError(f"{name} must be numeric") from exc
    if not minimum <= value <= maximum:
        raise RAGConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class RAGSettings:
    enabled: bool
    top_k: int
    minimum_similarity: float
    index_path: Path
    metadata_path: Path
    model_name: str
    debug: bool
    cache_size: int
    cache_ttl_seconds: int

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "RAGSettings":
        values = os.environ if env is None else env
        index_path = Path(values.get("RAG_INDEX_PATH", str(DEFAULT_INDEX_DIR))).expanduser()
        metadata_path = Path(
            values.get("RAG_METADATA_PATH", str(index_path / CHUNKS_FILENAME))
        ).expanduser()
        model_name = values.get("RAG_MODEL_NAME", DEFAULT_MODEL_NAME).strip()
        if not model_name:
            raise RAGConfigurationError("RAG_MODEL_NAME cannot be empty")
        return cls(
            enabled=_flag(values.get("RAG_ENABLED"), False),
            top_k=_integer(values, "RAG_TOP_K", 5, 1, 20),
            minimum_similarity=_floating(
                values, "RAG_MIN_SIMILARITY", 0.25, -1.0, 1.0
            ),
            index_path=index_path,
            metadata_path=metadata_path,
            model_name=model_name,
            debug=_flag(values.get("RAG_DEBUG"), False),
            cache_size=_integer(values, "RAG_CACHE_SIZE", 128, 0, 4096),
            cache_ttl_seconds=_integer(
                values, "RAG_CACHE_TTL_SECONDS", 300, 1, 86400
            ),
        )


@dataclass(frozen=True, slots=True)
class RAGHealth:
    enabled: bool
    ready: bool
    knowledge_base_version: str | None
    failure_reason: str | None


def _safe_failure_reason(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    if "missing" in name or "filenotfound" in name:
        return "index_missing"
    if "corrupt" in name:
        return "index_corrupt"
    if "incompatible" in name:
        return "index_incompatible"
    if isinstance(exc, RAGConfigurationError):
        return "configuration_invalid"
    return "rag_unavailable"


class RAGRuntime:
    """Initialize the model/index once and expose a thread-safe readiness state."""

    def __init__(
        self,
        settings: RAGSettings,
        *,
        configuration_error: Exception | None = None,
        retriever_factory=KnowledgeRetriever,
    ):
        self.settings = settings
        self._configuration_error = configuration_error
        self._retriever_factory = retriever_factory
        self._retriever: KnowledgeRetriever | None = None
        self._health = RAGHealth(settings.enabled, False, None, None)
        self._lock = threading.RLock()
        self._initialized = False

    def initialize(self) -> RAGHealth:
        with self._lock:
            if self._initialized:
                return self._health
            self._initialized = True
            if not self.settings.enabled:
                self._health = RAGHealth(False, False, None, None)
                logger.info("RAG startup validation skipped (enabled=false)")
                return self._health
            if self._configuration_error is not None:
                self._health = RAGHealth(True, False, None, "configuration_invalid")
                logger.error("RAG startup validation failed (reason=configuration_invalid)")
                return self._health

            try:
                retriever = self._retriever_factory(
                    index_dir=self.settings.index_path,
                    metadata_path=self.settings.metadata_path,
                    model_name=self.settings.model_name,
                    cache_size=self.settings.cache_size,
                    cache_ttl_seconds=self.settings.cache_ttl_seconds,
                )
                retriever.validate_ready()
                version = retriever.knowledge_base_version
                if not version:
                    raise RetrievalError("knowledge-base version is unavailable")
                self._retriever = retriever
                self._health = RAGHealth(True, True, version, None)
                logger.info(
                    "RAG startup validation complete (ready=true, chunk_count=%d)",
                    retriever.chunk_count,
                )
            except Exception as exc:
                reason = _safe_failure_reason(exc)
                self._health = RAGHealth(True, False, None, reason)
                logger.error(
                    "RAG startup validation failed (reason=%s, error_type=%s)",
                    reason,
                    type(exc).__name__,
                )
            return self._health

    @property
    def health(self) -> RAGHealth:
        return self.initialize()

    def get_retriever(self) -> KnowledgeRetriever:
        health = self.initialize()
        if not health.ready or self._retriever is None:
            raise RetrievalError(health.failure_reason or "RAG is not ready")
        return self._retriever


_runtime: RAGRuntime | None = None
_runtime_lock = threading.RLock()


def _fallback_settings() -> RAGSettings:
    return RAGSettings(
        enabled=os.getenv("RAG_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
        top_k=5,
        minimum_similarity=0.25,
        index_path=DEFAULT_INDEX_DIR,
        metadata_path=DEFAULT_INDEX_DIR / CHUNKS_FILENAME,
        model_name=DEFAULT_MODEL_NAME,
        debug=False,
        cache_size=128,
        cache_ttl_seconds=300,
    )


def get_rag_runtime() -> RAGRuntime:
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            try:
                _runtime = RAGRuntime(RAGSettings.from_env())
            except RAGConfigurationError as exc:
                _runtime = RAGRuntime(_fallback_settings(), configuration_error=exc)
        return _runtime


def get_runtime_retriever() -> KnowledgeRetriever:
    return get_rag_runtime().get_retriever()


def reset_rag_runtime_for_tests() -> None:
    global _runtime
    with _runtime_lock:
        _runtime = None
