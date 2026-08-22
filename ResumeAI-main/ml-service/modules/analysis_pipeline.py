"""Deterministic-first resume analysis with optional RAG feedback enrichment."""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from knowledge_base.query_builder import RetrievalQueryBuilder
from knowledge_base.schema import ALLOWED_ROLES
from modules.api_errors import FeedbackGenerationError
from modules.rag_runtime import get_rag_runtime, get_runtime_retriever
from modules.llm_insights import get_llm_insights
from modules.resume_quality import analyze_resume_quality
from modules.scorer import compute_skill_gap, compute_weighted_score
from modules.section_analyzer import analyze_sections
from modules.semantic_matcher import compute_similarity
from modules.skill_extractor import extract_skills_detailed


logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _safe_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def _safe_float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def infer_target_role(job_description: str) -> str:
    """Infer one supported role identifier from job-description terminology."""
    normalized = re.sub(r"[^a-z0-9+#.]+", " ", job_description.lower())
    role_patterns = (
        ("machine_learning_engineer", ("machine learning engineer", "ml engineer", "ai engineer")),
        ("data_analyst", ("data analyst", "business intelligence analyst", "bi analyst")),
        ("fullstack_developer", ("full stack", "fullstack", "full-stack")),
        ("frontend_developer", ("front end", "frontend", "front-end", "ui developer")),
        ("backend_developer", ("back end", "backend", "back-end", "api developer")),
    )
    for role, patterns in role_patterns:
        if any(pattern in normalized for pattern in patterns):
            return role
    return "software_engineer"


def _resolve_target_role(target_role: str | None, job_description: str) -> str:
    if target_role:
        normalized = target_role.strip().lower()
        if normalized in ALLOWED_ROLES:
            return normalized
        logger.warning("Ignoring unsupported target-role override; inferring from job description")
    return infer_target_role(job_description)


def _weak_sections(
    quality_report: dict[str, Any],
    section_scores: dict[str, Any],
) -> list[str]:
    weak: list[str] = []
    missing = (
        quality_report.get("details", {})
        .get("section_completeness", {})
        .get("sections_missing", [])
    )
    for section in missing:
        normalized = str(section).strip().lower()
        if normalized and normalized not in weak:
            weak.append(normalized)

    for section, raw_score in section_scores.items():
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        normalized = str(section).strip().lower()
        if score <= 5 and normalized and normalized not in weak:
            weak.append(normalized)
    return weak


def _detected_strengths(
    matched_skills: list[str],
    quality_report: dict[str, Any],
    section_scores: dict[str, Any],
) -> list[str]:
    strengths = [f"matched skill: {skill}" for skill in matched_skills[:5]]
    for dimension, raw_score in quality_report.get("scores", {}).items():
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        if score >= 0.80:
            strengths.append(f"strong quality area: {str(dimension).replace('_', ' ')}")
    for section, raw_score in section_scores.items():
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        if score >= 8:
            strengths.append(f"strong section: {str(section).lower()}")
    return strengths[:10]


def run_deterministic_analysis(
    *,
    resume_text: str,
    job_description: str,
    pdf_bytes: bytes | None,
) -> dict[str, Any]:
    """Run the pre-RAG analysis exactly, without retrieval or feedback generation."""
    resume_detailed = extract_skills_detailed(resume_text)
    resume_skills = resume_detailed["skills"]
    resume_categories = resume_detailed["by_category"]

    if job_description:
        jd_detailed = extract_skills_detailed(job_description)
        jd_skills = jd_detailed["skills"]
        jd_categories = jd_detailed["by_category"]
    else:
        jd_skills = []
        jd_categories = {}

    similarity_score = (
        compute_similarity(resume_text, job_description)
        if job_description
        else 0.0
    )
    skill_gap = compute_skill_gap(resume_skills, jd_skills)
    quality_report = analyze_resume_quality(resume_text, pdf_bytes)

    # Preserve the existing scoring arguments and ordering. RAG never enters this call.
    weighted_score = compute_weighted_score(
        skill_gap=skill_gap,
        similarity_score=similarity_score,
        resume_text=resume_text,
        job_description=job_description,
        quality_score=quality_report["overall"],
    )
    section_scores = analyze_sections(resume_text)
    weak_sections = _weak_sections(quality_report, section_scores)
    strengths = _detected_strengths(skill_gap["matched"], quality_report, section_scores)

    return {
        "resume_text": resume_text[:3000],
        "skills": resume_skills,
        "skill_categories": resume_categories,
        "jd_skills": jd_skills,
        "jd_categories": jd_categories,
        "skill_gap": skill_gap,
        "similarity_score": round(similarity_score, 4),
        "weighted_score": weighted_score,
        "resume_quality": quality_report,
        "section_scores": section_scores,
        "detected_strengths": strengths,
        "weak_sections": weak_sections,
    }


def _public_guidance(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "id",
        "role",
        "category",
        "title",
        "text",
        "source",
        "tags",
        "similarity_score",
        "rank",
    )
    return [{field: item[field] for field in fields if field in item} for item in results]


def run_analysis_pipeline(
    *,
    resume_text: str,
    job_description: str,
    pdf_bytes: bytes | None,
    target_role: str | None = None,
    rag_enabled: bool | None = None,
    request_id: str = "unknown",
) -> dict[str, Any]:
    """Run deterministic analysis, optional retrieval, and feedback generation."""
    deterministic = run_deterministic_analysis(
        resume_text=resume_text,
        job_description=job_description,
        pdf_bytes=pdf_bytes,
    )

    rag_settings = get_rag_runtime().settings
    enabled = rag_settings.enabled if rag_enabled is None else rag_enabled
    resolved_role = _resolve_target_role(target_role, job_description)
    rag = {
        "enabled": bool(enabled),
        "status": "disabled",
        "target_role": resolved_role,
        "retrieval_query": "",
        "retrieved_guidance": [],
        "retrieval_metadata": {
            "count": 0,
            "latency_ms": 0,
            "fallback_used": True,
            "source_ids": [],
            "fallback_reason": "disabled" if not enabled else None,
        },
    }
    retrieved_guidance: list[dict[str, Any]] = []

    if enabled:
        project_details = deterministic["resume_quality"].get("details", {}).get(
            "project_quality", {}
        )
        project_weaknesses = (
            project_details.get("notes", [])
            if float(project_details.get("score", 1.0)) < 0.65
            else []
        )
        is_fresher = (
            deterministic["resume_quality"].get("details", {})
            .get("resume_length", {})
            .get("is_fresher", False)
        )
        experience_level = "entry_level" if is_fresher else "experienced"

        try:
            query = RetrievalQueryBuilder().build(
                target_role=resolved_role,
                missing_skills=deterministic["skill_gap"]["missing"],
                weak_resume_sections=deterministic["weak_sections"],
                resume_quality_scores=deterministic["resume_quality"].get("scores", {}),
                job_description_keywords=deterministic["jd_skills"],
                experience_level=experience_level,
                project_weaknesses=project_weaknesses,
            )
            rag["retrieval_query"] = query
            logger.info(
                "RAG query constructed (request_id=%s, role=%s, length=%d, missing_skills=%d, weak_sections=%d)",
                request_id,
                resolved_role,
                len(query),
                len(deterministic["skill_gap"]["missing"]),
                len(deterministic["weak_sections"]),
            )

            started = time.perf_counter()
            retriever = get_runtime_retriever()
            retrieved_guidance = retriever.retrieve(
                query,
                target_role=resolved_role,
                top_k=rag_settings.top_k,
                minimum_similarity=rag_settings.minimum_similarity,
            )
            latency_ms = round((time.perf_counter() - started) * 1000)
            rag["retrieved_guidance"] = _public_guidance(retrieved_guidance)
            rag["retrieval_metadata"].update(
                {
                    "count": len(retrieved_guidance),
                    "latency_ms": latency_ms,
                    "source_ids": [item["id"] for item in retrieved_guidance],
                    "knowledge_base_version": getattr(retriever, "knowledge_base_version", None),
                }
            )
            logger.info(
                "RAG retrieval completed (request_id=%s, role=%s, count=%d, latency_ms=%d)",
                request_id,
                resolved_role,
                len(retrieved_guidance),
                latency_ms,
            )
            if retrieved_guidance:
                rag["status"] = "success"
                rag["retrieval_metadata"]["fallback_used"] = False
            else:
                rag["status"] = "no_results"
                rag["retrieval_metadata"]["fallback_reason"] = "no_results"
                logger.info("RAG fallback (request_id=%s, reason=no_results)", request_id)
        except Exception as exc:
            rag["status"] = "error"
            rag["retrieval_metadata"]["fallback_reason"] = "retrieval_error"
            logger.warning(
                "RAG fallback (request_id=%s, reason=retrieval_error, error_type=%s)",
                request_id,
                type(exc).__name__,
            )

    feedback_arguments = {
        "resume_text": resume_text,
        "job_description": job_description,
        "score": deterministic["weighted_score"]["final_score"],
        "missing_skills": deterministic["skill_gap"]["missing"],
        "matched_skills": deterministic["skill_gap"]["matched"],
        "request_id": request_id,
    }
    if retrieved_guidance:
        feedback_arguments.update(
            {
                "retrieved_guidance": retrieved_guidance,
                "retrieval_query": rag["retrieval_query"],
                "target_role": resolved_role,
                "detected_strengths": deterministic["detected_strengths"],
                "weak_sections": deterministic["weak_sections"],
                "deterministic_scores": {
                    "final_score": deterministic["weighted_score"]["final_score"],
                    "breakdown": deterministic["weighted_score"]["breakdown"],
                    "weights": deterministic["weighted_score"].get("weights", {}),
                    "semantic_similarity": deterministic["similarity_score"],
                    "resume_quality": deterministic["resume_quality"].get("scores", {}),
                    "section_scores": deterministic["section_scores"],
                },
            }
        )
    else:
        logger.info(
            "Generating feedback without retrieved guidance (request_id=%s, rag_status=%s)",
            request_id,
            rag["status"],
        )

    try:
        llm_insights = get_llm_insights(**feedback_arguments)
    except Exception as exc:
        logger.error(
            "Feedback generation failed (request_id=%s, error_type=%s)",
            request_id,
            type(exc).__name__,
        )
        raise FeedbackGenerationError("AI feedback generation failed") from exc
    if retrieved_guidance:
        cited_ids = llm_insights.get("source_ids", [])
        rag["retrieval_metadata"]["cited_source_ids"] = cited_ids
        if not cited_ids:
            rag["retrieval_metadata"]["fallback_used"] = True
            rag["retrieval_metadata"]["fallback_reason"] = "uncited_guidance"

    return {
        **deterministic,
        "llm_insights": llm_insights,
        "rag": rag,
    }
