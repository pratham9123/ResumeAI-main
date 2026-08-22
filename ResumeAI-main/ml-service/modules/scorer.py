"""
scorer.py
---------
Weighted scoring engine for resume analysis.

Improvements over v1:
- SCORING_WEIGHTS constant centralises all magic numbers.
- quality_score is now a required parameter (no silent inflation).
- _experience_score filters years to the lower 2/3 of the document
  to avoid education years inflating freshers' scores.
- Leadership keyword list expanded from 10 → 22 terms.
- skill_gap validation warns (instead of silently returning 0) on missing keys.
"""

import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


# ── Scoring weight config ──────────────────────────────────────────────────────
# Edit here — not inside function bodies.
# With-JD weights must sum to 1.0; No-JD weights must sum to 1.0.

SCORING_WEIGHTS = {
    "with_jd": {
        "core_skill_match":    0.40,
        "resume_quality":      0.40,
        "semantic_similarity": 0.10,
        "experience_signal":   0.10,
    },
    "no_jd": {
        "resume_quality":    0.90,
        "experience_signal": 0.10,
    },
}

# Sanity check at import time
assert abs(sum(SCORING_WEIGHTS["with_jd"].values()) - 1.0) < 1e-6, \
    "with_jd weights must sum to 1.0"
assert abs(sum(SCORING_WEIGHTS["no_jd"].values()) - 1.0) < 1e-6, \
    "no_jd weights must sum to 1.0"


# ── Leadership / impact keywords ───────────────────────────────────────────────
_LEADERSHIP_KW = [
    # Original 10
    "led", "managed", "architected", "designed", "built",
    "founded", "spearheaded", "owned", "delivered", "launched",
    # Added
    "coordinated", "oversaw", "supervised", "guided", "facilitated",
    "initiated", "transformed", "executed", "championed", "directed",
    "mentored", "established",
]


def compute_skill_gap(resume_skills: List[str], jd_skills: List[str]) -> Dict:
    """
    Compute matched, missing, and extra skills between resume and JD.
    """
    resume_set = set(s.lower() for s in resume_skills)
    jd_set     = set(s.lower() for s in jd_skills)

    matched = sorted(resume_set & jd_set)
    missing = sorted(jd_set - resume_set)   # In JD but NOT in resume
    extra   = sorted(resume_set - jd_set)   # In resume but NOT in JD

    return {
        "matched":     matched,
        "missing":     missing,
        "extra":       extra,
        "match_ratio": len(matched) / len(jd_set) if jd_set else 0.0,
    }


def compute_weighted_score(
    skill_gap:        Dict,
    similarity_score: float,
    resume_text:      str,
    job_description:  str,
    quality_score:    float,          # Required — no silent default inflation
) -> Dict:
    """
    Multi-dimensional weighted scoring formula.

    With JD:
        Score = skill_match * 0.40
              + quality    * 0.40
              + semantic   * 0.10
              + experience * 0.10

    Without JD (pure resume quality evaluation):
        Score = quality  * 0.90
              + experience * 0.10
    """
    has_jd = bool(job_description and job_description.strip())

    # Validate skill_gap dict
    if "match_ratio" not in skill_gap:
        logger.warning(
            "skill_gap missing 'match_ratio' key — defaulting to 0.0. "
            "Check compute_skill_gap() caller."
        )
    core       = skill_gap.get("match_ratio", 0.0)
    secondary  = float(similarity_score)
    experience = _experience_score(resume_text)

    w = SCORING_WEIGHTS["with_jd"] if has_jd else SCORING_WEIGHTS["no_jd"]

    if has_jd:
        raw = (
            core          * w["core_skill_match"] +
            quality_score * w["resume_quality"] +
            secondary     * w["semantic_similarity"] +
            experience    * w["experience_signal"]
        )
    else:
        raw = quality_score * w["resume_quality"] + experience * w["experience_signal"]

    final_score = round(min(max(raw * 100, 0), 100))

    return {
        "final_score": final_score,
        "breakdown": {
            "core":       round(core, 4),
            "secondary":  round(secondary, 4),
            "experience": round(experience, 4),
            "quality":    round(quality_score, 4),
        },
        "weights": w,
    }


def _experience_score(resume_text: str) -> float:
    """
    Adaptive heuristic experience signal.

    Fixes over v1:
    - Only considers years found in the **lower two-thirds** of the document,
      so education years at the top don't inflate freshers' scores.
    - Leadership keyword list expanded to 22 terms.

    Returns a value in [0.0, 1.0].
    """
    text_lower = resume_text.lower()
    score      = 0.50   # neutral base

    # ── Year span — lower 2/3 of document only ────────────────────────────
    cutoff    = len(resume_text) // 3          # first 1/3 is usually header+education
    body_text = resume_text[cutoff:]
    years     = [int(y) for y in re.findall(r"\b(20\d{2}|19[89]\d)\b", body_text)]

    if len(years) >= 2:
        span = max(years) - min(years)
        if span >= 5:
            score = 1.0
        elif span >= 3:
            score = 0.85
        elif span >= 1:
            score = 0.70
        # span == 0  → stays at 0.50 (same year, e.g. a single internship)

    # ── Leadership / impact keywords (each +2.5%, capped) ────────────────
    found_kw = sum(1 for kw in _LEADERSHIP_KW if kw in text_lower)
    score    = min(score + found_kw * 0.025, 1.0)

    # ── Internship boost for freshers ─────────────────────────────────────
    if "intern" in text_lower and score < 0.75:
        score = min(score + 0.10, 1.0)

    return round(score, 4)
