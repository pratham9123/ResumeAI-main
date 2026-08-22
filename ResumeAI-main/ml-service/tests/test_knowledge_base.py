from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knowledge_base.loader import load_knowledge_base, load_knowledge_chunks
from knowledge_base.schema import (
    ALLOWED_ROLES,
    KnowledgeChunk,
    KnowledgeValidationError,
)


REQUIRED_CATEGORIES = {
    "professional_summary",
    "technical_skills",
    "project_descriptions",
    "work_experience",
    "measurable_impact",
    "action_verbs",
    "ats_formatting",
    "role_keywords",
    "common_mistakes",
    "bullet_examples",
    "claim_quality",
    "project_architecture",
}


def _valid_chunk(chunk_id: str = "general.test.01") -> dict:
    return {
        "id": chunk_id,
        "role": "general",
        "category": "professional_summary",
        "title": "A valid test chunk",
        "text": "This guidance is deliberately long enough to satisfy the minimum validation length.",
        "source": "ResumeAI test fixture",
        "tags": ["Summary Advice", "evidence"],
    }


class KnowledgeSchemaTests(unittest.TestCase):
    def test_schema_normalizes_whitespace_and_tags(self):
        payload = _valid_chunk()
        payload["title"] = "  A   valid   title  "
        payload["tags"] = ["Summary Advice", "summary advice", "ATS"]

        chunk = KnowledgeChunk.from_dict(payload)

        self.assertEqual(chunk.title, "A valid title")
        self.assertEqual(chunk.tags, ("summary_advice", "ats"))
        self.assertEqual(chunk.to_dict()["tags"], ["summary_advice", "ats"])

    def test_schema_rejects_missing_unknown_and_invalid_role_fields(self):
        missing = _valid_chunk()
        del missing["text"]
        with self.assertRaisesRegex(KnowledgeValidationError, "missing required"):
            KnowledgeChunk.from_dict(missing)

        unknown = _valid_chunk()
        unknown["extra"] = True
        with self.assertRaisesRegex(KnowledgeValidationError, "unknown field"):
            KnowledgeChunk.from_dict(unknown)

        invalid_role = _valid_chunk()
        invalid_role["role"] = "wizard"
        with self.assertRaisesRegex(KnowledgeValidationError, "unsupported role"):
            KnowledgeChunk.from_dict(invalid_role)


class KnowledgeLoaderTests(unittest.TestCase):
    def test_seed_corpus_is_valid_complete_and_unique(self):
        result = load_knowledge_base()

        self.assertEqual(result.issues, [])
        self.assertEqual(result.files_scanned, 7)
        self.assertEqual(result.entries_scanned, 42)
        self.assertEqual(len(result.chunks), 42)
        self.assertEqual({chunk.role for chunk in result.chunks}, ALLOWED_ROLES)
        self.assertTrue(REQUIRED_CATEGORIES.issubset({c.category for c in result.chunks}))
        self.assertEqual(len({chunk.id for chunk in result.chunks}), len(result.chunks))

    def test_loader_skips_malformed_entry_and_later_duplicate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = _valid_chunk("general.duplicate.01")
            malformed = _valid_chunk("general.invalid.01")
            malformed["tags"] = []
            duplicate = _valid_chunk("general.duplicate.01")
            duplicate["title"] = "This duplicate should be skipped"

            (root / "a.json").write_text(
                json.dumps({"chunks": [first, malformed]}), encoding="utf-8"
            )
            (root / "b.json").write_text(
                json.dumps({"chunks": [duplicate]}), encoding="utf-8"
            )

            result = load_knowledge_base(root)

        self.assertEqual([chunk.id for chunk in result.chunks], ["general.duplicate.01"])
        self.assertEqual(len(result.issues), 2)
        self.assertTrue(any("non-empty JSON array" in issue.message for issue in result.issues))
        self.assertTrue(any("duplicate id" in issue.message for issue in result.issues))

    def test_loader_reports_invalid_json_and_strict_mode_raises(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "broken.json").write_text("{not-json", encoding="utf-8")

            result = load_knowledge_base(root)
            self.assertEqual(result.chunks, [])
            self.assertEqual(len(result.issues), 1)

            with self.assertRaisesRegex(KnowledgeValidationError, "1 issue"):
                load_knowledge_chunks(root, strict=True)

    def test_normalized_list_api_returns_json_serializable_dicts(self):
        chunks = load_knowledge_chunks(strict=True)

        self.assertEqual(len(chunks), 42)
        self.assertIsInstance(chunks[0], dict)
        self.assertIsInstance(chunks[0]["tags"], list)
        json.dumps(chunks)


if __name__ == "__main__":
    unittest.main()
