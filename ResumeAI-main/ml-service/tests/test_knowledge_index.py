from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from knowledge_base.indexing import (
    CONFIG_FILENAME,
    INDEX_FILENAME,
    CHUNKS_FILENAME,
    CorruptIndexError,
    EmptyKnowledgeBaseError,
    IncompatibleIndexError,
    MissingIndexMetadataError,
    ensure_knowledge_index,
    load_index_bundle,
)
from modules.embedding_service import DEFAULT_MODEL_NAME, EmbeddingError


class FakeEmbedder:
    """Deterministic test double that exercises indexing without model downloads."""

    def __init__(self, dimension: int = 8):
        self.model_name = DEFAULT_MODEL_NAME
        self.dimension = dimension
        self.calls = 0
        self.encoded_text_count = 0

    def encode(self, texts):
        self.calls += 1
        self.encoded_text_count += len(texts)
        rows = []
        for position, text in enumerate(texts):
            values = np.zeros(self.dimension, dtype=np.float32)
            encoded = text.encode("utf-8")
            for index, value in enumerate(encoded):
                values[index % self.dimension] += (value + position + 1) / 255.0
            rows.append(values)
        return np.asarray(rows, dtype=np.float32)


class InvalidEmbedder(FakeEmbedder):
    def encode(self, texts):
        return np.full((len(texts), self.dimension), np.nan, dtype=np.float32)


class KnowledgeIndexTests(unittest.TestCase):
    def test_embeddings_are_generated_normalized_and_indexed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            embedder = FakeEmbedder(dimension=8)
            result = ensure_knowledge_index(index_dir=temp_dir, embedder=embedder)

            self.assertTrue(result.rebuilt)
            self.assertEqual(embedder.calls, 1)
            self.assertEqual(embedder.encoded_text_count, 42)
            self.assertEqual(result.bundle.index.ntotal, 42)
            self.assertEqual(result.bundle.index.d, 8)
            self.assertEqual(result.bundle.config["embedding_dimension"], 8)

            reconstructed = result.bundle.index.reconstruct_n(0, 42)
            np.testing.assert_allclose(
                np.linalg.norm(reconstructed, axis=1),
                np.ones(42),
                rtol=1e-5,
                atol=1e-5,
            )

    def test_saved_artifacts_load_and_unchanged_corpus_is_reused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            embedder = FakeEmbedder()
            first = ensure_knowledge_index(index_dir=root, embedder=embedder)
            created_at = first.bundle.config["created_at"]

            self.assertTrue((root / INDEX_FILENAME).is_file())
            self.assertTrue((root / CHUNKS_FILENAME).is_file())
            self.assertTrue((root / CONFIG_FILENAME).is_file())

            loaded = load_index_bundle(root)
            self.assertEqual(loaded.index.ntotal, 42)
            self.assertEqual(len(loaded.chunks), 42)

            second = ensure_knowledge_index(index_dir=root, embedder=embedder)
            self.assertFalse(second.rebuilt)
            self.assertEqual(second.action, "reused")
            self.assertEqual(embedder.calls, 1)
            self.assertEqual(second.bundle.config["created_at"], created_at)

    def test_empty_knowledge_base_is_rejected(self):
        with tempfile.TemporaryDirectory() as empty_data, tempfile.TemporaryDirectory() as index_dir:
            with self.assertRaisesRegex(EmptyKnowledgeBaseError, "empty knowledge base"):
                ensure_knowledge_index(
                    data_dir=empty_data,
                    index_dir=index_dir,
                    embedder=FakeEmbedder(),
                )

    def test_invalid_embedding_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(EmbeddingError, "NaN or infinite"):
                ensure_knowledge_index(index_dir=temp_dir, embedder=InvalidEmbedder())

    def test_missing_and_corrupt_artifacts_raise_clear_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(MissingIndexMetadataError, "missing index configuration"):
                load_index_bundle(root)

            ensure_knowledge_index(index_dir=root, embedder=FakeEmbedder())
            (root / INDEX_FILENAME).write_bytes(b"not a faiss index")
            with self.assertRaisesRegex(CorruptIndexError, "could not read FAISS index"):
                load_index_bundle(root)

    def test_incompatible_faiss_dimension_is_detected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ensure_knowledge_index(index_dir=root, embedder=FakeEmbedder(dimension=8))
            config_path = root / CONFIG_FILENAME
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["embedding_dimension"] = 16
            config_path.write_text(json.dumps(config), encoding="utf-8")

            with self.assertRaisesRegex(IncompatibleIndexError, "FAISS dimension 8"):
                load_index_bundle(root)


if __name__ == "__main__":
    unittest.main()
