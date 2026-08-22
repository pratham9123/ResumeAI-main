from __future__ import annotations

import math
import unittest
from pathlib import Path

import faiss
import numpy as np

from knowledge_base.indexing import IndexPaths, KnowledgeIndexBundle
from knowledge_base.retriever import KnowledgeRetriever
from knowledge_base.schema import KnowledgeChunk
from modules.embedding_service import DEFAULT_MODEL_NAME
from modules.rag_runtime import (
    RAGConfigurationError,
    RAGRuntime,
    RAGSettings,
)


class FakeReadyRetriever:
    chunk_count = 42
    knowledge_base_version = "checksum-v1"

    def __init__(self, calls, **kwargs):
        calls["kwargs"] = kwargs
        self.calls = calls

    def validate_ready(self):
        self.calls["validated"] = True


class CountingEmbedder:
    model_name = DEFAULT_MODEL_NAME

    def __init__(self):
        self.calls = 0

    def encode(self, texts):
        self.calls += 1
        return np.asarray([[1.0, 0.0] for _ in texts], dtype=np.float32)


def settings(enabled=True):
    return RAGSettings(
        enabled=enabled,
        top_k=5,
        minimum_similarity=0.25,
        index_path=Path("index"),
        metadata_path=Path("index/chunks.json"),
        model_name=DEFAULT_MODEL_NAME,
        debug=False,
        cache_size=8,
        cache_ttl_seconds=60,
    )


class RAGRuntimeTests(unittest.TestCase):
    def test_environment_configuration_is_validated(self):
        parsed = RAGSettings.from_env(
            {
                "RAG_ENABLED": "true",
                "RAG_TOP_K": "7",
                "RAG_MIN_SIMILARITY": "0.4",
                "RAG_INDEX_PATH": "custom-index",
                "RAG_METADATA_PATH": "custom-index/meta.json",
                "RAG_MODEL_NAME": DEFAULT_MODEL_NAME,
                "RAG_DEBUG": "true",
                "RAG_CACHE_SIZE": "12",
                "RAG_CACHE_TTL_SECONDS": "90",
            }
        )
        self.assertTrue(parsed.enabled)
        self.assertEqual(parsed.top_k, 7)
        self.assertEqual(parsed.metadata_path, Path("custom-index/meta.json"))
        self.assertTrue(parsed.debug)

        with self.assertRaises(RAGConfigurationError):
            RAGSettings.from_env({"RAG_TOP_K": "0"})

    def test_enabled_runtime_validates_once_and_reports_safe_health(self):
        calls = {}

        def factory(**kwargs):
            return FakeReadyRetriever(calls, **kwargs)

        runtime = RAGRuntime(settings(), retriever_factory=factory)
        first = runtime.initialize()
        second = runtime.initialize()

        self.assertIs(first, second)
        self.assertTrue(first.ready)
        self.assertEqual(first.knowledge_base_version, "checksum-v1")
        self.assertTrue(calls["validated"])
        self.assertEqual(calls["kwargs"]["cache_size"], 8)

    def test_startup_failure_degrades_without_exposing_paths(self):
        runtime = RAGRuntime(
            settings(),
            retriever_factory=lambda **_kwargs: (_ for _ in ()).throw(
                FileNotFoundError("C:/private/index/knowledge.faiss")
            ),
        )
        health = runtime.initialize()

        self.assertTrue(health.enabled)
        self.assertFalse(health.ready)
        self.assertEqual(health.failure_reason, "index_missing")
        self.assertNotIn("private", health.failure_reason)

    def test_disabled_runtime_does_not_load_model_or_index(self):
        runtime = RAGRuntime(
            settings(enabled=False),
            retriever_factory=lambda **_kwargs: self.fail("factory should not run"),
        )
        self.assertFalse(runtime.initialize().ready)


class RetrievalCacheTests(unittest.TestCase):
    def test_cache_reuses_results_without_retaining_plaintext_key(self):
        chunk = KnowledgeChunk.from_dict(
            {
                "id": "backend.cache.01",
                "role": "backend_developer",
                "category": "project_bullets",
                "title": "Backend cache guidance",
                "text": "Describe backend project boundaries, verified impact, and deployment responsibilities clearly.",
                "source": "ResumeAI test guidance",
                "tags": ["backend", "cache"],
            }
        )
        index = faiss.IndexFlatIP(2)
        score = 0.9
        index.add(np.asarray([[score, math.sqrt(1 - score * score)]], dtype=np.float32))
        bundle = KnowledgeIndexBundle(
            index=index,
            chunks=[chunk],
            config={
                "model_name": DEFAULT_MODEL_NAME,
                "embedding_dimension": 2,
                "knowledge_base_checksum": "checksum",
            },
            paths=IndexPaths.from_root(Path("unused")),
        )
        embedder = CountingEmbedder()
        retriever = KnowledgeRetriever(
            bundle=bundle,
            embedder=embedder,
            cache_size=4,
            cache_ttl_seconds=60,
        )
        query = "backend guidance without personal information"

        first = retriever.retrieve(query, target_role="backend_developer", minimum_similarity=0)
        first[0]["title"] = "mutated"
        second = retriever.retrieve(query, target_role="backend_developer", minimum_similarity=0)

        self.assertEqual(embedder.calls, 1)
        self.assertEqual(second[0]["title"], "Backend cache guidance")
        self.assertTrue(all(query not in key for key in retriever._result_cache))


if __name__ == "__main__":
    unittest.main()
