from __future__ import annotations

import io
import unittest
from unittest.mock import patch

import app as flask_app
from modules.api_errors import FeedbackGenerationError


LEGACY_FIELDS = {
    "resume_text",
    "skills",
    "skill_categories",
    "jd_skills",
    "jd_categories",
    "skill_gap",
    "similarity_score",
    "weighted_score",
    "resume_quality",
    "section_scores",
    "llm_insights",
}


def _pipeline_result(*, enabled=True, status="success", fallback=False):
    guidance = []
    cited_ids = []
    if status == "success":
        guidance = [
            {
                "id": "backend_developer.project_bullets.01",
                "role": "backend_developer",
                "category": "project_bullets",
                "title": "Backend project bullet guidance",
                "text": "Internal guidance text must not be public by default.",
                "source": "ResumeAI curated guidance",
                "tags": ["backend", "projects"],
                "similarity_score": 0.78123,
                "rank": 1,
            }
        ]
        cited_ids = ["backend_developer.project_bullets.01"]

    return {
        "resume_text": "Extracted resume preview",
        "skills": ["python"],
        "skill_categories": {"Programming Languages": ["python"]},
        "jd_skills": ["python", "docker"],
        "jd_categories": {"Tools": ["docker"]},
        "skill_gap": {
            "matched": ["python"],
            "missing": ["docker"],
            "extra": [],
            "match_ratio": 0.5,
        },
        "similarity_score": 0.54,
        "weighted_score": {"final_score": 67, "breakdown": {}},
        "resume_quality": {"overall": 0.7, "scores": {}, "details": {}},
        "section_scores": {"projects": 6},
        "detected_strengths": ["matched skill: python"],
        "weak_sections": ["projects"],
        "llm_insights": {"feedback": "Improve project evidence.", "suggestions": []},
        "rag": {
            "enabled": enabled,
            "status": status,
            "target_role": "backend_developer",
            "retrieval_query": "Internal query",
            "retrieved_guidance": guidance,
            "retrieval_metadata": {
                "count": len(guidance),
                "latency_ms": 12,
                "fallback_used": fallback,
                "source_ids": [item["id"] for item in guidance],
                "cited_source_ids": cited_ids,
            },
        },
    }


def _multipart(*, target_role="backend_developer", include_resume=True, include_jd=True):
    data = {}
    if include_resume:
        data["resume"] = (io.BytesIO(b"%PDF test resume"), "resume.pdf")
    if include_jd:
        data["job_description"] = "Backend developer role requiring Python and Docker."
    if target_role is not None:
        data["target_role"] = target_role
    return data


class FlaskAnalyzeAPITests(unittest.TestCase):
    def setUp(self):
        flask_app.app.config.update(TESTING=True)
        self.client = flask_app.app.test_client()
        self.extracted_text = "Experienced backend developer. " * 4

    def _post(self, data):
        return self.client.post(
            "/analyze", data=data, content_type="multipart/form-data"
        )

    @patch.object(flask_app, "run_analysis_pipeline")
    @patch.object(flask_app, "extract_text_from_pdf")
    def test_rag_success_returns_compact_evidence(self, extract, pipeline):
        extract.return_value = self.extracted_text
        pipeline.return_value = _pipeline_result()

        response = self._post(_multipart())
        body = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["rag"]["enabled"])
        self.assertTrue(body["rag"]["used"])
        self.assertFalse(body["rag"]["fallbackUsed"])
        self.assertEqual(body["rag"]["retrievedCount"], 1)
        self.assertEqual(
            body["rag"]["sources"][0],
            {
                "id": "backend_developer.project_bullets.01",
                "title": "Backend project bullet guidance",
                "category": "project_bullets",
                "similarityScore": 0.7812,
            },
        )
        self.assertNotIn("text", body["rag"]["sources"][0])
        self.assertNotIn("debug", body["rag"])

    @patch.object(flask_app, "run_analysis_pipeline")
    @patch.object(flask_app, "extract_text_from_pdf")
    def test_rag_disabled_preserves_non_rag_response(self, extract, pipeline):
        extract.return_value = self.extracted_text
        pipeline.return_value = _pipeline_result(
            enabled=False, status="disabled", fallback=True
        )

        response = self._post(_multipart())
        rag = response.get_json()["rag"]

        self.assertEqual(response.status_code, 200)
        self.assertFalse(rag["enabled"])
        self.assertFalse(rag["used"])
        self.assertFalse(rag["fallbackUsed"])

    def test_invalid_target_role_is_validation_error(self):
        response = self._post(_multipart(target_role="astronaut"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error_type"], "validation_error")

    def test_missing_resume_is_validation_error(self):
        response = self._post(_multipart(include_resume=False))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error_type"], "validation_error")

    def test_missing_job_description_is_validation_error(self):
        response = self._post(_multipart(include_jd=False))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error_type"], "validation_error")

    @patch.object(flask_app, "MAX_RESUME_BYTES", 8)
    def test_oversized_resume_is_rejected(self):
        response = self._post(_multipart())

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.get_json()["error_type"], "validation_error")

    @patch.object(flask_app, "run_analysis_pipeline")
    @patch.object(flask_app, "extract_text_from_pdf")
    def test_gemini_boundary_failure_returns_502(self, extract, pipeline):
        extract.return_value = self.extracted_text
        pipeline.side_effect = FeedbackGenerationError("provider failed")

        response = self._post(_multipart())

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["error_type"], "feedback_error")
        self.assertNotIn("provider failed", response.get_data(as_text=True))

    @patch.object(flask_app, "run_analysis_pipeline")
    @patch.object(flask_app, "extract_text_from_pdf")
    def test_retriever_failure_is_a_successful_fallback(self, extract, pipeline):
        extract.return_value = self.extracted_text
        pipeline.return_value = _pipeline_result(
            enabled=True, status="error", fallback=True
        )

        response = self._post(_multipart())
        rag = response.get_json()["rag"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(rag["status"], "error")
        self.assertFalse(rag["used"])
        self.assertTrue(rag["fallbackUsed"])
        self.assertEqual(rag["sources"], [])

    @patch.object(flask_app, "run_analysis_pipeline")
    @patch.object(flask_app, "extract_text_from_pdf")
    def test_legacy_response_fields_remain_present(self, extract, pipeline):
        extract.return_value = self.extracted_text
        pipeline.return_value = _pipeline_result()

        response = self._post(_multipart())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(LEGACY_FIELDS.issubset(response.get_json()))


if __name__ == "__main__":
    unittest.main()
