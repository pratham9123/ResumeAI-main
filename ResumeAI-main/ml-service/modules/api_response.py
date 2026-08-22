"""Shape internal analysis results for the public Flask API."""

from __future__ import annotations

import math
from typing import Any


LEGACY_RESPONSE_FIELDS = (
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
)


def _similarity_score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return round(score, 4) if math.isfinite(score) else None


def _source_evidence(guidance: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for chunk in guidance:
        chunk_id = str(chunk.get("id", "")).strip()
        if not chunk_id:
            continue
        source = {
            "id": chunk_id,
            "title": str(chunk.get("title", "")).strip(),
            "category": str(chunk.get("category", "")).strip(),
            "similarityScore": _similarity_score(chunk.get("similarity_score")),
        }
        sources.append(source)
    return sources


def build_analysis_response(
    result: dict[str, Any], *, include_rag_debug: bool = False
) -> dict[str, Any]:
    """Preserve legacy fields while exposing only safe RAG evidence by default."""
    response = {
        field: result[field]
        for field in LEGACY_RESPONSE_FIELDS
        if field in result
    }
    for field in ("detected_strengths", "weak_sections"):
        if field in result:
            response[field] = result[field]

    internal_rag = result.get("rag") or {}
    metadata = internal_rag.get("retrieval_metadata") or {}
    guidance = internal_rag.get("retrieved_guidance") or []
    enabled = bool(internal_rag.get("enabled", False))
    status = str(internal_rag.get("status", "disabled"))
    cited_ids = {
        str(source_id)
        for source_id in metadata.get("cited_source_ids", [])
        if str(source_id).strip()
    }
    sources = _source_evidence(guidance)

    public_rag: dict[str, Any] = {
        "status": status,
        "enabled": enabled,
        "used": enabled and status == "success" and bool(cited_ids),
        "fallbackUsed": enabled and bool(metadata.get("fallback_used", False)),
        "retrievedCount": int(metadata.get("count", len(sources)) or 0),
        "sources": sources,
    }
    if metadata.get("knowledge_base_version"):
        public_rag["knowledgeBaseVersion"] = metadata["knowledge_base_version"]

    if include_rag_debug:
        public_rag["debug"] = {
            "status": status,
            "targetRole": internal_rag.get("target_role"),
            "retrievalQuery": internal_rag.get("retrieval_query", ""),
            "retrievedGuidance": guidance,
            "retrievalMetadata": metadata,
        }

    response["rag"] = public_rag
    return response
