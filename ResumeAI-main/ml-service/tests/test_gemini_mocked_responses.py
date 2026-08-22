from __future__ import annotations

import copy
import json
import os
import unittest
from unittest.mock import patch

from modules.llm_insights import get_llm_insights
from tests.test_llm_grounding import GUIDANCE, RESUME_TEXT, SOURCE_ID, _valid_response


class MockedGeminiResponseTests(unittest.TestCase):
    def _generate(self, grounded_response, *, retrieved_guidance=None):
        prompts = []

        def fake_gemini(prompt, api_key, *, response_parser=None):
            prompts.append(prompt)
            if "RETRIEVED_KNOWLEDGE_REFERENCE" in prompt:
                return response_parser(grounded_response)
            return response_parser(
                json.dumps(
                    {
                        "feedback": "The legacy fallback returned safe concise feedback.",
                        "suggestions": ["Use only verified resume evidence."],
                    }
                )
            )

        environment = {
            "GOOGLE_GEMINI_API_KEY": "test-key",
            "GEMINI_API_KEY": "",
            "OPENAI_API_KEY": "",
        }
        with patch.dict(os.environ, environment, clear=False), patch(
            "modules.llm_insights._call_gemini", side_effect=fake_gemini
        ):
            result = get_llm_insights(
                resume_text=RESUME_TEXT,
                job_description="Backend role requiring unit testing",
                score=63,
                missing_skills=["unit testing"],
                matched_skills=["python"],
                retrieved_guidance=retrieved_guidance,
                retrieval_query="Backend project guidance",
                deterministic_scores={"final_score": 63},
                detected_strengths=["verified latency improvement"],
                weak_sections=["projects"],
                target_role="backend_developer",
            )
        return result, prompts

    def test_valid_json_response(self):
        result, prompts = self._generate(
            json.dumps(_valid_response()), retrieved_guidance=[GUIDANCE]
        )
        self.assertIn("summary", result)
        self.assertEqual(result["source_ids"], [SOURCE_ID])
        self.assertEqual(len(prompts), 1)

    def test_json_inside_markdown_fences(self):
        fenced = f"```json\n{json.dumps(_valid_response())}\n```"
        result, _ = self._generate(fenced, retrieved_guidance=[GUIDANCE])
        self.assertIn("summary", result)

    def test_missing_fields_trigger_legacy_fallback(self):
        payload = _valid_response()
        del payload["confidence"]
        result, prompts = self._generate(
            json.dumps(payload), retrieved_guidance=[GUIDANCE]
        )
        self.assertNotIn("summary", result)
        self.assertEqual(len(prompts), 2)

    def test_malformed_output_triggers_legacy_fallback(self):
        result, prompts = self._generate("not-json", retrieved_guidance=[GUIDANCE])
        self.assertNotIn("summary", result)
        self.assertEqual(len(prompts), 2)

    def test_fabricated_metric_triggers_legacy_fallback(self):
        payload = _valid_response()
        payload["rewritten_bullets"][0]["improved"] = "Reduced API latency by 75%."
        result, _ = self._generate(
            json.dumps(payload), retrieved_guidance=[GUIDANCE]
        )
        self.assertNotIn("summary", result)

    def test_unknown_source_id_triggers_legacy_fallback(self):
        payload = _valid_response()
        payload["priority_actions"][0]["source_ids"] = ["unknown.source.01"]
        result, _ = self._generate(
            json.dumps(payload), retrieved_guidance=[GUIDANCE]
        )
        self.assertNotIn("summary", result)

    def test_empty_retrieved_context_uses_only_legacy_prompt(self):
        result, prompts = self._generate(
            json.dumps(_valid_response()), retrieved_guidance=[]
        )
        self.assertEqual(set(result), {"feedback", "suggestions"})
        self.assertEqual(len(prompts), 1)
        self.assertNotIn("RETRIEVED_KNOWLEDGE_REFERENCE", prompts[0])


if __name__ == "__main__":
    unittest.main()
