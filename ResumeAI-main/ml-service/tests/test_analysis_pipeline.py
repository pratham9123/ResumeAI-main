from __future__ import annotations

import unittest

from modules.api_errors import FeedbackGenerationError
from modules.analysis_pipeline import (
    run_analysis_pipeline,
    run_deterministic_analysis,
)


GUIDANCE = {
    "id": "backend_developer.bullet_examples.01",
    "role": "backend_developer",
    "category": "bullet_examples",
    "title": "Replace a vague API bullet",
    "text": "Describe the API method, constraint, measured behavior, and result with defensible evidence.",
    "source": "ResumeAI test guidance",
    "tags": ["backend", "bullets"],
    "similarity_score": 0.72,
    "rank": 1,
}


class FakeQueryBuilder:
    def __init__(self, calls):
        self.calls = calls

    def build(self, **kwargs):
        self.calls["query_builder"] = kwargs
        return "Resume improvement guidance for a backend candidate with weak project bullets."


class FakeRetriever:
    def __init__(self, calls, result=None, error=None):
        self.calls = calls
        self.result = result if result is not None else []
        self.error = error

    def retrieve(self, query, **kwargs):
        self.calls["retriever"] = {"query": query, **kwargs}
        if self.error:
            raise self.error
        return self.result


def _dependencies(test_case, *, retrieval_result=None, retrieval_error=None, feedback_error=None):
    calls = {}

    def skill_extractor(text):
        if text == "JOB DESCRIPTION":
            return {
                "skills": ["java", "unit testing", "docker"],
                "by_category": {"Programming Languages": ["java"]},
            }
        return {
            "skills": ["python", "docker"],
            "by_category": {"Programming Languages": ["python"]},
        }

    def similarity_calculator(resume_text, job_description):
        calls["similarity_inputs"] = (resume_text, job_description)
        return 0.42

    def skill_gap_calculator(resume_skills, jd_skills):
        return {
            "matched": ["docker"],
            "missing": ["java", "unit testing"],
            "extra": ["python"],
            "match_ratio": 1 / 3,
        }

    def quality_analyzer(resume_text, pdf_bytes):
        return {
            "overall": 0.61,
            "scores": {
                "section_completeness": 0.50,
                "achievements_quality": 0.40,
                "ats_compatibility": 0.90,
                "project_quality": 0.30,
            },
            "details": {
                "section_completeness": {"sections_missing": ["summary"]},
                "project_quality": {
                    "score": 0.30,
                    "notes": ["project bullets lack measurable impact"],
                },
                "resume_length": {"is_fresher": True},
            },
        }

    def score_calculator(**kwargs):
        calls["score_arguments"] = kwargs
        return {
            "final_score": 58,
            "breakdown": {
                "core": 0.3333,
                "secondary": 0.42,
                "experience": 0.60,
                "quality": 0.61,
            },
            "weights": {
                "core_skill_match": 0.40,
                "resume_quality": 0.40,
                "semantic_similarity": 0.10,
                "experience_signal": 0.10,
            },
        }

    def section_analyzer(resume_text):
        return {"Projects": 4, "Skills": 9}

    def feedback_generator(**kwargs):
        calls["feedback"] = kwargs
        if feedback_error:
            raise feedback_error
        result = {
            "feedback": "The candidate has useful backend evidence but should make project impact clearer.",
            "suggestions": ["Rewrite one project bullet with a measured result."],
        }
        if kwargs.get("retrieved_guidance"):
            result["source_ids"] = [GUIDANCE["id"]]
        return result

    import unittest.mock as mock
    patchers = [
        mock.patch("modules.analysis_pipeline.extract_skills_detailed", side_effect=skill_extractor),
        mock.patch("modules.analysis_pipeline.compute_similarity", side_effect=similarity_calculator),
        mock.patch("modules.analysis_pipeline.compute_skill_gap", side_effect=skill_gap_calculator),
        mock.patch("modules.analysis_pipeline.analyze_resume_quality", side_effect=quality_analyzer),
        mock.patch("modules.analysis_pipeline.compute_weighted_score", side_effect=score_calculator),
        mock.patch("modules.analysis_pipeline.analyze_sections", side_effect=section_analyzer),
        mock.patch("modules.analysis_pipeline.get_llm_insights", side_effect=feedback_generator),
        mock.patch("modules.analysis_pipeline.RetrievalQueryBuilder", return_value=FakeQueryBuilder(calls)),
        mock.patch("modules.analysis_pipeline.get_runtime_retriever", return_value=FakeRetriever(calls, result=retrieval_result, error=retrieval_error)),
    ]
    for p in patchers:
        p.start()
        test_case.addCleanup(p.stop)
    
    return calls


class AnalysisPipelineTests(unittest.TestCase):
    def _run(self, rag_enabled):
        return run_analysis_pipeline(
            resume_text="RESUME TEXT WITH PROJECT AND EXPERIENCE DETAILS",
            job_description="JOB DESCRIPTION",
            pdf_bytes=b"pdf",
            target_role="backend_developer",
            rag_enabled=rag_enabled,
        )

    def test_successful_rag_flow(self):
        calls = _dependencies(self, retrieval_result=[GUIDANCE])
        result = self._run(rag_enabled=True)

        self.assertEqual(result["rag"]["status"], "success")
        self.assertEqual(result["rag"]["retrieval_metadata"]["count"], 1)
        self.assertFalse(result["rag"]["retrieval_metadata"]["fallback_used"])
        self.assertEqual(result["rag"]["retrieval_metadata"]["cited_source_ids"], [GUIDANCE["id"]])
        self.assertEqual(result["rag"]["retrieved_guidance"][0]["id"], GUIDANCE["id"])
        self.assertIn("retrieved_guidance", calls["feedback"])
        self.assertIn("retrieval_query", calls["feedback"])

    def test_rag_disabled_uses_existing_feedback_flow(self):
        calls = _dependencies(self, retrieval_result=[GUIDANCE])
        result = self._run(rag_enabled=False)

        self.assertEqual(result["rag"]["status"], "disabled")
        self.assertNotIn("retriever", calls)
        self.assertNotIn("query_builder", calls)
        self.assertNotIn("retrieved_guidance", calls["feedback"])
        self.assertEqual(result["llm_insights"]["feedback"], calls["feedback"] and result["llm_insights"]["feedback"])

    def test_empty_retrieval_falls_back_without_failing(self):
        calls = _dependencies(self, retrieval_result=[])
        result = self._run(rag_enabled=True)

        self.assertEqual(result["rag"]["status"], "no_results")
        self.assertTrue(result["rag"]["retrieval_metadata"]["fallback_used"])
        self.assertNotIn("retrieved_guidance", calls["feedback"])
        self.assertIn("feedback", result["llm_insights"])

    def test_retriever_exception_falls_back_without_failing(self):
        calls = _dependencies(self, retrieval_error=RuntimeError("index unavailable"))
        result = self._run(rag_enabled=True)

        self.assertEqual(result["rag"]["status"], "error")
        self.assertTrue(result["rag"]["retrieval_metadata"]["fallback_used"])
        self.assertNotIn("retrieved_guidance", calls["feedback"])
        self.assertEqual(result["weighted_score"]["final_score"], 58)

    def test_missing_index_falls_back_to_non_rag_feedback(self):
        calls = _dependencies(
            self,
            retrieval_error=FileNotFoundError("knowledge.faiss is unavailable")
        )
        result = self._run(rag_enabled=True)

        self.assertEqual(result["rag"]["status"], "error")
        self.assertEqual(
            result["rag"]["retrieval_metadata"]["fallback_reason"],
            "retrieval_error",
        )
        self.assertNotIn("retrieved_guidance", calls["feedback"])
        self.assertEqual(result["weighted_score"]["final_score"], 58)

    def test_gemini_failure_is_reported_without_changing_deterministic_analysis(self):
        calls = _dependencies(
            self,
            retrieval_result=[GUIDANCE],
            feedback_error=RuntimeError("mocked Gemini outage"),
        )
        deterministic = run_deterministic_analysis(
            resume_text="RESUME TEXT WITH PROJECT AND EXPERIENCE DETAILS",
            job_description="JOB DESCRIPTION",
            pdf_bytes=b"pdf",
        )

        with self.assertRaisesRegex(FeedbackGenerationError, "AI feedback generation failed"):
            self._run(rag_enabled=True)

        self.assertEqual(deterministic["weighted_score"]["final_score"], 58)
        self.assertEqual(deterministic["similarity_score"], 0.42)
    def test_deterministic_outputs_are_identical_with_rag_enrichment(self):
        calls = _dependencies(self, retrieval_result=[GUIDANCE])
        arguments = {
            "resume_text": "RESUME TEXT WITH PROJECT AND EXPERIENCE DETAILS",
            "job_description": "JOB DESCRIPTION",
            "pdf_bytes": b"pdf",
        }
        deterministic = run_deterministic_analysis(**arguments)
        enriched = run_analysis_pipeline(
            **arguments,
            target_role="backend_developer",
            rag_enabled=True,
        )

        for field in (
            "skills",
            "skill_categories",
            "jd_skills",
            "jd_categories",
            "skill_gap",
            "similarity_score",
            "weighted_score",
            "resume_quality",
            "section_scores",
            "weak_sections",
        ):
            self.assertEqual(enriched[field], deterministic[field], field)
        self.assertEqual(
            enriched["weighted_score"]["weights"],
            {
                "core_skill_match": 0.40,
                "resume_quality": 0.40,
                "semantic_similarity": 0.10,
                "experience_signal": 0.10,
            },
        )

    def test_response_remains_backward_compatible(self):
        calls = _dependencies(self, retrieval_result=[GUIDANCE])
        result = self._run(rag_enabled=True)

        original_fields = {
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
        self.assertTrue(original_fields.issubset(result))
        self.assertIn("feedback", result["llm_insights"])
        self.assertIn("suggestions", result["llm_insights"])


if __name__ == "__main__":
    unittest.main()
