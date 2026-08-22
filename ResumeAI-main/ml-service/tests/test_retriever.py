from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import faiss
import numpy as np

from knowledge_base.indexing import IndexPaths, KnowledgeIndexBundle
from knowledge_base.query_builder import (
    QueryBuilderValidationError,
    RetrievalQueryBuilder,
)
from knowledge_base.retriever import (
    KnowledgeRetriever,
    RetrievalValidationError,
)
from knowledge_base.schema import KnowledgeChunk
from modules.embedding_service import DEFAULT_MODEL_NAME


class QueryEmbedder:
    model_name = DEFAULT_MODEL_NAME

    def __init__(self):
        self.calls = 0

    def encode(self, texts):
        self.calls += 1
        return np.asarray([[1.0, 0.0] for _ in texts], dtype=np.float32)


def _unit_vector(score: float) -> list[float]:
    return [score, math.sqrt(max(0.0, 1.0 - score * score))]


def _chunk(chunk_id: str, role: str, category: str, text: str) -> KnowledgeChunk:
    return KnowledgeChunk.from_dict(
        {
            "id": chunk_id,
            "role": role,
            "category": category,
            "title": f"Guidance for {chunk_id}",
            "text": text,
            "source": "ResumeAI retrieval test fixture",
            "tags": ["testing", category],
        }
    )


def _bundle(chunks, scores) -> KnowledgeIndexBundle:
    index = faiss.IndexFlatIP(2)
    index.add(np.asarray([_unit_vector(score) for score in scores], dtype=np.float32))
    return KnowledgeIndexBundle(
        index=index,
        chunks=chunks,
        config={"model_name": DEFAULT_MODEL_NAME},
        paths=IndexPaths.from_root(Path("unused-test-index")),
    )


class RetrieverTests(unittest.TestCase):
    def setUp(self):
        duplicate_text = (
            "Describe the API method, technical constraint, measured latency, and verified "
            "result instead of making an unsupported scalability claim."
        )
        self.chunks = [
            _chunk(
                "frontend.noise.01",
                "frontend_developer",
                "project_descriptions",
                "Explain component state, user interaction, accessibility, and measured frontend performance.",
            ),
            _chunk(
                "software.noise.01",
                "software_engineer",
                "technical_skills",
                "Group software engineering languages, frameworks, test tools, and delivery systems clearly.",
            ),
            _chunk("backend.primary.01", "backend_developer", "bullet_examples", duplicate_text),
            _chunk("backend.duplicate.01", "backend_developer", "bullet_examples", duplicate_text),
            _chunk(
                "general.impact.01",
                "general",
                "measurable_impact",
                "Use defensible measures such as time saved, latency, adoption, throughput, or error reduction.",
            ),
            _chunk(
                "backend.architecture.01",
                "backend_developer",
                "project_architecture",
                "Explain API boundaries, persistence, asynchronous work, failure handling, and one design trade-off.",
            ),
            _chunk(
                "data.noise.01",
                "data_analyst",
                "work_experience",
                "Connect the analytical question, dataset, method, stakeholder decision, and business outcome.",
            ),
        ]
        self.bundle = _bundle(self.chunks, [1.0, 0.995, 0.98, 0.97, 0.85, 0.75, 0.99])
        self.embedder = QueryEmbedder()
        self.retriever = KnowledgeRetriever(bundle=self.bundle, embedder=self.embedder)

    def test_role_filtering_and_general_guidance_inclusion(self):
        results = self.retriever.retrieve(
            "backend resume guidance",
            target_role="backend_developer",
            top_k=3,
            minimum_similarity=0.0,
        )

        self.assertEqual(
            [result["id"] for result in results],
            ["backend.primary.01", "general.impact.01", "backend.architecture.01"],
        )
        self.assertEqual({result["role"] for result in results}, {"backend_developer", "general"})
        self.assertNotIn("frontend.noise.01", {result["id"] for result in results})

    def test_similarity_threshold_and_zero_matches(self):
        results = self.retriever.retrieve(
            "backend resume guidance",
            target_role="backend_developer",
            top_k=5,
            minimum_similarity=0.90,
        )
        self.assertEqual([result["id"] for result in results], ["backend.primary.01"])

        none = self.retriever.retrieve(
            "backend resume guidance",
            target_role="backend_developer",
            minimum_similarity=0.999,
        )
        self.assertEqual(none, [])

    def test_results_are_ordered_ranked_and_limited_by_top_k(self):
        results = self.retriever.retrieve(
            "backend resume guidance",
            target_role="backend_developer",
            top_k=2,
            minimum_similarity=0.0,
        )

        self.assertEqual(len(results), 2)
        self.assertEqual([item["rank"] for item in results], [1, 2])
        self.assertGreaterEqual(results[0]["similarity_score"], results[1]["similarity_score"])

    def test_duplicate_and_near_identical_results_are_suppressed(self):
        results = self.retriever.retrieve(
            "backend bullet guidance",
            target_role="backend_developer",
            top_k=5,
            minimum_similarity=0.0,
        )
        ids = {result["id"] for result in results}
        self.assertIn("backend.primary.01", ids)
        self.assertNotIn("backend.duplicate.01", ids)

    def test_optional_category_filter_applies_to_role_and_general_chunks(self):
        results = self.retriever.retrieve(
            "measurable impact",
            target_role="backend_developer",
            categories=["measurable_impact"],
            minimum_similarity=0.0,
        )
        self.assertEqual([result["id"] for result in results], ["general.impact.01"])

    def test_invalid_role_and_empty_query_are_rejected(self):
        with self.assertRaisesRegex(RetrievalValidationError, "unsupported target role"):
            self.retriever.retrieve("guidance", target_role="wizard")
        with self.assertRaisesRegex(RetrievalValidationError, "cannot be empty"):
            self.retriever.retrieve("  ", target_role="backend_developer")

    def test_overfetch_expands_when_initial_candidates_are_filtered_out(self):
        distractors = [
            _chunk(
                f"frontend.distractor.{index:02d}",
                "frontend_developer",
                "technical_skills",
                f"Frontend distractor guidance number {index} with enough content for schema validation.",
            )
            for index in range(25)
        ]
        relevant = _chunk(
            "backend.late.01",
            "backend_developer",
            "technical_skills",
            "Relevant backend guidance that appears below the initial over-fetched candidate window.",
        )
        scores = [0.99 - index * 0.01 for index in range(25)] + [0.40]
        retriever = KnowledgeRetriever(
            bundle=_bundle(distractors + [relevant], scores),
            embedder=QueryEmbedder(),
        )

        results = retriever.retrieve(
            "backend skills",
            target_role="backend_developer",
            top_k=1,
            minimum_similarity=0.0,
        )
        self.assertEqual([result["id"] for result in results], ["backend.late.01"])


class RetrievalQueryBuilderTests(unittest.TestCase):
    def test_builder_uses_analysis_signals_without_raw_resume_content(self):
        query = RetrievalQueryBuilder().build(
            target_role="software_engineer",
            missing_skills=["Java", "unit testing", "person@example.com"],
            weak_resume_sections=["projects"],
            resume_quality_scores={
                "achievements_quality": 0.42,
                "ats_compatibility": 0.91,
            },
            job_description_keywords=["backend deployment", "https://private.example"],
            experience_level="entry_level",
            project_weaknesses=["bullets lack measurable impact", "+91 98765 43210"],
        )

        self.assertIn("software engineering candidate", query)
        self.assertIn("Java", query)
        self.assertIn("unit testing", query)
        self.assertIn("achievements quality", query)
        self.assertIn("bullets lack measurable impact", query)
        self.assertNotIn("person@example.com", query)
        self.assertNotIn("private.example", query)
        self.assertNotIn("98765", query)
        self.assertNotIn("ats compatibility", query)
        self.assertLessEqual(len(query), 900)

    def test_builder_rejects_invalid_role(self):
        with self.assertRaisesRegex(QueryBuilderValidationError, "unsupported target role"):
            RetrievalQueryBuilder().build(target_role="wizard")


if __name__ == "__main__":
    unittest.main()
