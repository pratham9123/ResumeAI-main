"""Build concise, non-PII retrieval queries from deterministic analysis output."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .schema import ALLOWED_ROLES


_ROLE_LABELS = {
    "software_engineer": "software engineering",
    "backend_developer": "backend development",
    "frontend_developer": "frontend development",
    "fullstack_developer": "full-stack development",
    "data_analyst": "data analysis",
    "machine_learning_engineer": "machine learning engineering",
    "general": "general",
}
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b", re.IGNORECASE)
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_SAFE_TERM = re.compile(r"[^a-zA-Z0-9+#./&()_-]+")


class QueryBuilderValidationError(ValueError):
    """Raised when analysis signals cannot produce a safe retrieval query."""


def _safe_term(value: Any, *, maximum_length: int = 60) -> str:
    if not isinstance(value, str):
        return ""
    compact = " ".join(value.split())
    if not compact or _EMAIL.search(compact) or _URL.search(compact) or _PHONE.search(compact):
        return ""
    compact = _SAFE_TERM.sub(" ", compact)
    return " ".join(compact.split())[:maximum_length].strip()


def _safe_terms(values: Sequence[Any] | None, *, limit: int) -> list[str]:
    if not values:
        return []
    output = []
    for value in values:
        normalized = _safe_term(value)
        if normalized and normalized.lower() not in {term.lower() for term in output}:
            output.append(normalized)
        if len(output) >= limit:
            break
    return output


def _display(value: str) -> str:
    return value.replace("_", " ").replace("-", " ")


class RetrievalQueryBuilder:
    """Convert derived resume-analysis signals into a short semantic intent."""

    def __init__(self, weak_quality_threshold: float = 0.65):
        if not 0.0 <= weak_quality_threshold <= 1.0:
            raise ValueError("weak_quality_threshold must be between 0 and 1")
        self.weak_quality_threshold = weak_quality_threshold

    def build(
        self,
        *,
        target_role: str,
        missing_skills: Sequence[str] | None = None,
        weak_resume_sections: Sequence[str] | None = None,
        resume_quality_scores: Mapping[str, Any] | None = None,
        job_description_keywords: Sequence[str] | None = None,
        experience_level: str | None = None,
        project_weaknesses: Sequence[str] | None = None,
    ) -> str:
        role = str(target_role).strip().lower()
        if role not in ALLOWED_ROLES:
            allowed = ", ".join(sorted(ALLOWED_ROLES))
            raise QueryBuilderValidationError(
                f"unsupported target role '{role}'; expected one of: {allowed}"
            )

        missing = _safe_terms(missing_skills, limit=8)
        weak_sections = _safe_terms(weak_resume_sections, limit=6)
        jd_keywords = _safe_terms(job_description_keywords, limit=8)
        project_issues = _safe_terms(project_weaknesses, limit=5)
        level = _safe_term(experience_level or "", maximum_length=30)

        weak_quality: list[tuple[float, str]] = []
        for name, raw_score in (resume_quality_scores or {}).items():
            safe_name = _safe_term(str(name), maximum_length=40)
            if not safe_name or isinstance(raw_score, bool):
                continue
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                continue
            normalized_score = score / 100.0 if score > 1.0 else score
            if 0.0 <= normalized_score < self.weak_quality_threshold:
                weak_quality.append((normalized_score, safe_name))
        weak_quality.sort(key=lambda item: (item[0], item[1]))

        role_label = _ROLE_LABELS[role]
        opening = f"Resume improvement guidance for a {role_label} candidate"
        if level:
            opening += f" with {_display(level)} experience"
        clauses = []
        if missing:
            clauses.append(f"missing or underrepresented skills: {', '.join(missing)}")
        if weak_sections:
            clauses.append(f"weak resume sections: {', '.join(map(_display, weak_sections))}")
        if weak_quality:
            names = [_display(name) for _, name in weak_quality[:5]]
            clauses.append(f"low resume-quality areas: {', '.join(names)}")
        if jd_keywords:
            clauses.append(
                "job-description keywords needing truthful coverage: "
                + ", ".join(jd_keywords)
            )
        if project_issues:
            clauses.append(f"project weaknesses: {', '.join(project_issues)}")

        if clauses:
            query = opening + " whose priorities include " + "; ".join(clauses) + "."
        else:
            query = opening + " focused on ATS-compatible, evidence-based improvements."

        return query[:900]
