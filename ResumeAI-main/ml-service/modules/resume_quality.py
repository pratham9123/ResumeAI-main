"""
resume_quality.py
-----------------
Multi-dimensional resume quality analyzer.

Dimensions:
  1. Section Completeness      – are standard sections present as headings?
  2. ATS Compatibility         – tables, special chars, emoji, standard headings
  3. Chronological Order       – latest experience first?
  4. Achievements Quality      – action verbs + quantification
  5. Contact Info Validity     – email, phone, LinkedIn, GitHub
  6. Readability               – bullet points, line length, structure
  7. Resume Length             – word count / page appropriateness
  8. Project Quality           – tech stack, links, impact (freshers)
  9. Keyword Density           – important terms repeated naturally
 10. Formatting Consistency    – font sizes / families via pdfplumber chars

Improvements over v1:
- Section detection requires keywords on short lines (≤ 60 chars) as headings.
- Chronological order checked only after first section heading position.
- Resume length: word_count > 800 no longer treated as "experienced" signal.
- Keyword density uses ~60-word stopword set instead of 14.
- Formatting weight raised to 0.04 (was 0.00 — computed but unused).
- ATS check covers emoji and Unicode arrows/symbols.
- Bullet ratio threshold is fresher-aware.
- QUALITY_WEIGHTS documented and asserted to sum to 1.0.
"""

import re
import io
import logging
from collections import Counter
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

SECTION_KEYWORDS = {
    "education":    ["education", "academic", "qualification", "degree",
                     "university", "college", "school"],
    "skills":       ["skills", "technical skills", "technologies", "tech stack",
                     "competencies", "expertise", "tools"],
    "experience":   ["experience", "work experience", "employment",
                     "professional experience", "work history", "internship"],
    "projects":     ["projects", "personal projects", "academic projects",
                     "portfolio", "open source"],
    "achievements": ["achievements", "accomplishments", "awards",
                     "certifications", "honors", "hackathon"],
    "summary":      ["summary", "objective", "profile", "about me",
                     "overview", "career objective"],
}

ACTION_VERBS = [
    "led", "built", "developed", "designed", "implemented", "architected",
    "created", "managed", "optimized", "improved", "reduced", "increased",
    "delivered", "launched", "engineered", "automated", "integrated",
    "collaborated", "mentored", "spearheaded", "drove", "achieved",
    "established", "streamlined", "deployed", "maintained", "analyzed",
    "researched", "solved", "trained", "evaluated", "contributed",
    "published", "presented", "won", "earned", "demonstrated", "utilized",
    "migrated", "refactored", "debugged", "scaled",
]

IMPACT_WORDS = [
    "improved", "reduced", "increased", "optimized", "achieved", "delivered",
    "saved", "generated", "boosted", "accelerated", "enhanced", "minimized",
]

QUANTIFICATION_PATTERNS = [
    r"\d+\s*%",
    r"\d+\s*x\b",
    r"\$\s*\d+",
    r"\d+\s*[KkMmBb]\b",
    r"\b\d{2,}\s+(?:users|records|requests|transactions|members|projects|features|tests|issues|bugs)\b",
]

DEMO_KEYWORDS    = ["deployed", "live", "demo", "vercel", "netlify", "heroku",
                    "render", "production", "launch"]
IMPACT_KEYWORDS  = ["users", "reduced", "improved", "optimized", "real-time",
                    "scalable", "production", "million", "thousand"]

# Expanded stopword set (~60 words) for keyword density check
_STOPWORDS = {
    "the", "and", "for", "are", "was", "with", "that", "this", "from",
    "have", "been", "will", "your", "using", "used", "also", "well",
    "more", "each", "both", "when", "then", "than", "into", "such",
    "where", "they", "them", "their", "which", "what", "over", "about",
    "team", "work", "make", "time", "include", "able", "would", "could",
    "should", "other", "after", "while", "within", "without", "between",
    "through", "across", "based", "during", "before", "under", "these",
    "those", "some", "same", "very", "just",
}


# ── Helper: detect heading lines ───────────────────────────────────────────────

def _heading_lines(text_lower: str) -> List[str]:
    """
    Return lines that look like section headings:
    short (≤ 60 chars), non-empty, not just punctuation.
    """
    return [
        line.strip()
        for line in text_lower.splitlines()
        if 0 < len(line.strip()) <= 60 and re.search(r'[a-z]', line)
    ]


def _first_section_position(resume_text: str) -> int:
    """
    Return the character position of the first section heading in the document.
    Falls back to 0 if none found.
    """
    all_kws = [kw for kws in SECTION_KEYWORDS.values() for kw in kws]
    for line in resume_text.splitlines():
        stripped = line.strip()
        if 0 < len(stripped) <= 60:
            line_lower = stripped.lower()
            if any(kw in line_lower for kw in all_kws):
                return resume_text.find(line)
    return 0


# ── Sub-evaluators ─────────────────────────────────────────────────────────────

def check_section_completeness(text_lower: str) -> Dict:
    """
    Check that standard resume sections appear as actual headings
    (short lines ≤ 60 chars), not just anywhere in body text.
    """
    headings = _heading_lines(text_lower)

    def _section_in_headings(keywords: List[str]) -> bool:
        return any(
            any(kw in h for kw in keywords)
            for h in headings
        )

    found = {s: _section_in_headings(kws) for s, kws in SECTION_KEYWORDS.items()}

    critical  = ["education", "skills"]
    important = ["projects", "experience"]
    nice      = ["achievements", "summary"]

    critical_score  = sum(found.get(s, False) for s in critical)  / len(critical)
    important_score = sum(found.get(s, False) for s in important) / len(important)
    nice_score      = sum(found.get(s, False) for s in nice)      / len(nice)

    score = critical_score * 0.55 + important_score * 0.35 + nice_score * 0.10

    return {
        "score":            round(score, 4),
        "sections_found":   [s for s, v in found.items() if v],
        "sections_missing": [s for s in (critical + important) if not found.get(s)],
    }


def check_ats_compatibility(resume_text: str, pdf_bytes: Optional[bytes]) -> Dict:
    """ATS friendliness: no tables, standard headings, no heavy symbols or emoji."""
    issues = []
    score  = 1.0
    text_lower = resume_text.lower()

    # Standard headings present?
    standard_headings = ["education", "skills", "experience", "projects"]
    missing_headings  = [h for h in standard_headings if h not in text_lower]
    if len(missing_headings) > 1:
        score -= 0.15 * len(missing_headings) / len(standard_headings)
        issues.append(f"Non-standard section headings: {', '.join(missing_headings)}")

    # Special symbols ATS can't parse (expanded + emoji Unicode blocks)
    ats_unfriendly = re.findall(
        r"[★✦✓●►▶■□▪✔➤→←↑↓✗✘⚡]"       # common arrow/check symbols
        r"|[\U0001F000-\U0001FFFF]"       # emoji (Mahjong tiles → flags)
        r"|[\u2600-\u27BF]",              # misc symbols, dingbats
        resume_text
    )
    if len(ats_unfriendly) > 5:
        score -= 0.15
        issues.append(
            f"Heavy use of special characters/emoji ({len(ats_unfriendly)} found) "
            "— ATS systems may misread them"
        )

    # Tables inside PDF
    if pdf_bytes:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables and any(len(t) > 1 for t in tables):
                        score -= 0.25
                        issues.append(
                            "Tables detected — ATS systems often cannot parse tables"
                        )
                        break
        except Exception:
            pass

    # Email present
    if not re.search(r"[\w.+-]+@[\w-]+\.\w+", resume_text):
        score -= 0.10
        issues.append("No email address found — required for ATS")

    return {
        "score":           round(max(score, 0.0), 4),
        "issues":          issues,
        "is_ats_friendly": score >= 0.75,
    }


def check_chronological_order(resume_text: str) -> Dict:
    """
    Check if experience is listed in reverse chronological order.

    Improvement: only searches for years AFTER the first section heading,
    avoiding header/contact dates from skewing the result.
    """
    first_section = _first_section_position(resume_text)
    body_text     = resume_text[first_section:]

    year_positions = [
        (int(m.group()), m.start())
        for m in re.finditer(r"\b(20\d{2}|19[89]\d)\b", body_text)
    ]

    if len(year_positions) < 2:
        return {
            "score": 0.75,
            "note":  "Not enough date information to verify order",
            "years_found": [],
        }

    years_only = sorted(set(y for y, _ in year_positions), reverse=True)

    mid         = len(body_text) // 2
    first_half  = [y for y, pos in year_positions if pos < mid]
    second_half = [y for y, pos in year_positions if pos >= mid]

    if first_half and second_half:
        if max(first_half) >= max(second_half):
            return {
                "score": 1.0,
                "note":  "Reverse chronological order confirmed",
                "years_found": years_only,
            }
        else:
            return {
                "score": 0.5,
                "note":  "Experience may NOT be in reverse chronological order",
                "years_found": years_only,
            }

    return {
        "score": 0.75,
        "note":  "Could not definitively verify order",
        "years_found": years_only,
    }


def check_achievements_quality(resume_text: str) -> Dict:
    """Evaluate action verbs, quantification, and impact language."""
    text_lower = resume_text.lower()

    found_verbs = [v for v in ACTION_VERBS if re.search(r"\b" + v + r"\b", text_lower)]
    verb_score  = min(len(found_verbs) / 6, 1.0)

    quant_matches = []
    for pattern in QUANTIFICATION_PATTERNS:
        quant_matches.extend(re.findall(pattern, resume_text, re.IGNORECASE))
    quant_score = min(len(quant_matches) / 3, 1.0)

    impact_found = [w for w in IMPACT_WORDS if w in text_lower]
    impact_score = min(len(impact_found) / 3, 1.0)

    score = verb_score * 0.40 + quant_score * 0.40 + impact_score * 0.20

    suggestions = []
    if verb_score < 0.5:
        suggestions.append("Use more action verbs (Led, Built, Optimized, Achieved...)")
    if quant_score < 0.5:
        suggestions.append(
            "Quantify achievements (e.g., 'reduced load time by 30%', "
            "'trained on 5000 records')"
        )

    return {
        "score":               round(score, 4),
        "action_verbs_found":  found_verbs[:10],
        "quantifications":     len(quant_matches),
        "impact_words_found":  impact_found,
        "suggestions":         suggestions,
    }


def check_contact_info(resume_text: str) -> Dict:
    """Validate presence of email, phone, LinkedIn, GitHub."""
    checks = {
        "email":    bool(re.search(r"[\w.+-]+@[\w-]+\.\w+", resume_text)),
        "phone":    bool(re.search(r"(\+?\d[\d\s\-(). ]{7,14}\d)", resume_text)),
        "linkedin": bool(re.search(r"linkedin\.com", resume_text, re.IGNORECASE)),
        "github":   bool(re.search(r"github\.com", resume_text, re.IGNORECASE)),
    }

    score = (
        (0.35 if checks["email"]    else 0) +
        (0.25 if checks["phone"]    else 0) +
        (0.25 if checks["linkedin"] else 0) +
        (0.15 if checks["github"]   else 0)
    )

    missing = [k for k, v in checks.items() if not v]
    return {
        "score":   round(min(score, 1.0), 4),
        "checks":  checks,
        "missing": missing,
    }


def check_readability(resume_text: str, is_fresher: bool = False) -> Dict:
    """
    Score based on bullet point usage, line length, and whitespace structure.

    Improvement: bullet ratio threshold is lower for freshers (0.15 vs 0.25)
    because skills-heavy fresher resumes naturally have fewer bullet lines.
    """
    score = 0.5
    notes = []

    lines     = resume_text.split("\n")
    non_empty = [l.strip() for l in lines if l.strip()]

    bullet_lines = [l for l in non_empty if re.match(r"^[•\-\*–▸◦·]", l)]
    bullet_ratio = len(bullet_lines) / max(len(non_empty), 1)
    threshold    = 0.15 if is_fresher else 0.25

    if bullet_ratio > threshold:
        score += 0.25
        notes.append("Good use of bullet points for scannability")
    else:
        notes.append("Consider converting paragraphs to bullet points")

    avg_len = sum(len(l) for l in non_empty) / max(len(non_empty), 1)
    if avg_len < 110:
        score += 0.15
        notes.append("Line lengths are readable")
    else:
        notes.append("Some lines are too long — break them up")

    empty_ratio = (len(lines) - len(non_empty)) / max(len(lines), 1)
    if 0.10 < empty_ratio < 0.40:
        score += 0.10
        notes.append("Good whitespace / section separation")

    return {
        "score":           round(min(score, 1.0), 4),
        "bullet_ratio":    round(bullet_ratio, 2),
        "avg_line_length": round(avg_len, 1),
        "notes":           notes,
    }


def check_resume_length(resume_text: str, pdf_bytes: Optional[bytes]) -> Dict:
    """
    Score based on word count and page appropriateness.

    Improvement: only explicit work-experience keywords determine fresher/experienced,
    NOT word count (a verbose fresher project section shouldn't trigger "experienced").
    """
    page_count = 1
    if pdf_bytes:
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                page_count = len(pdf.pages)
        except Exception:
            pass

    word_count = len(resume_text.split())

    # Only keyword presence (not word count) determines experience level
    exp_kws = [
        "work experience", "professional experience",
        "employment history", "job title",
    ]
    is_experienced = any(kw in resume_text.lower() for kw in exp_kws)

    if not is_experienced:          # Fresher: 1 page ideal
        if 200 <= word_count <= 700:
            score, note = 1.0, "Ideal length for a fresher resume (1 page)"
        elif word_count < 200:
            score, note = 0.45, "Resume is too short — add more detail in projects/skills"
        else:
            score, note = 0.70, "Resume may be too long for a fresher — aim for 1 page"
    else:                           # Experienced: 1-2 pages
        if 400 <= word_count <= 1100:
            score, note = 1.0, "Ideal resume length (1-2 pages)"
        elif word_count < 400:
            score, note = 0.55, "Resume is too brief for an experienced candidate"
        else:
            score, note = 0.65, "Resume may be too long — trim to 2 pages max"

    return {
        "score":      score,
        "page_count": page_count,
        "word_count": word_count,
        "is_fresher": not is_experienced,
        "note":       note,
    }


def check_project_quality(text_lower: str) -> Dict:
    """Evaluate project section quality — especially important for freshers."""
    score = 0.0
    notes = []

    tech_patterns = [
        "tools & technologies", "tools and technologies", "built using",
        "built with", "tech stack", "technologies used",
    ]
    if any(p in text_lower for p in tech_patterns):
        score += 0.30
        notes.append("Tech stack clearly stated in projects")

    if "github.com" in text_lower:
        score += 0.25
        notes.append("GitHub link present")
    elif "github" in text_lower:
        score += 0.10
        notes.append("GitHub mentioned (add full URL for better ATS)")

    if any(kw in text_lower for kw in DEMO_KEYWORDS):
        score += 0.20
        notes.append("Deployment or live demo mentioned")

    impact_count = sum(1 for kw in IMPACT_KEYWORDS if kw in text_lower)
    if impact_count >= 3:
        score += 0.25
        notes.append("Real-world impact and scale described")
    elif impact_count >= 1:
        score += 0.10

    if not notes:
        notes.append(
            "Add GitHub URLs, tech stack, and measurable impact to project descriptions"
        )

    return {"score": round(min(score, 1.0), 4), "notes": notes}


def check_keyword_density(resume_text: str) -> Dict:
    """
    Check whether important technical terms appear repeatedly (good for ATS).
    Uses an expanded ~60-word stopword set.
    """
    words     = re.findall(r"\b[a-zA-Z][a-zA-Z0-9.+#\-]{2,}\b", resume_text.lower())
    word_freq = Counter(words)

    tech_repeated = sum(
        1 for word, count in word_freq.most_common(60)
        if count > 1 and len(word) > 3 and word not in _STOPWORDS
    )

    score = min(tech_repeated / 12, 1.0)

    return {
        "score":               round(score, 4),
        "top_keywords":        [w for w, _ in word_freq.most_common(12)
                                if w not in _STOPWORDS],
        "tech_repeated_count": tech_repeated,
    }


def check_formatting(pdf_bytes: Optional[bytes]) -> Dict:
    """Analyze font size and family consistency via pdfplumber char data."""
    if not pdf_bytes:
        return {"score": 0.70, "note": "Formatting analysis requires PDF"}

    try:
        import pdfplumber
        font_sizes, font_families = [], []

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                for char in page.chars:
                    if char.get("size"):
                        font_sizes.append(round(float(char["size"]), 1))
                    if char.get("fontname"):
                        base = re.sub(
                            r"[-,](Bold|Italic|Regular|Medium|Light|Black|Oblique).*",
                            "", char["fontname"], flags=re.IGNORECASE
                        )
                        font_families.append(base)

        if not font_sizes:
            return {"score": 0.70, "note": "Could not extract font information from PDF"}

        unique_sizes    = len(set(font_sizes))
        unique_families = len(set(font_families))
        score, notes    = 1.0, []

        if unique_sizes > 6:
            score -= 0.20
            notes.append(
                f"Too many font sizes ({unique_sizes}) "
                "— aim for 2-3 sizes (body, heading, subheading)"
            )
        elif 2 <= unique_sizes <= 4:
            notes.append("Consistent font sizing")

        if unique_families > 3:
            score -= 0.20
            notes.append(
                f"Multiple font families ({unique_families}) "
                "— stick to 1-2 for a professional look"
            )
        elif unique_families <= 2:
            notes.append("Consistent font family")

        return {
            "score":                round(max(score, 0.0), 4),
            "unique_font_sizes":    unique_sizes,
            "unique_font_families": unique_families,
            "notes":                notes,
        }

    except Exception as e:
        return {"score": 0.70, "note": f"Formatting analysis error: {e}"}


# ── Weights ─────────────────────────────────────────────────────────────────────
# Must sum to exactly 1.0.
# Formatting raised to 0.04 (from 0.00) — it now contributes to the score.
# Section completeness reduced from 0.18 to 0.14 to compensate.

QUALITY_WEIGHTS = {
    "section_completeness": 0.14,
    "achievements_quality": 0.18,
    "ats_compatibility":    0.14,
    "project_quality":      0.14,
    "contact_info":         0.10,
    "chronological_order":  0.08,
    "readability":          0.08,
    "keyword_density":      0.06,
    "resume_length":        0.04,
    "formatting":           0.04,
}

_total_w = sum(QUALITY_WEIGHTS.values())
if abs(_total_w - 1.0) > 1e-6:
    logger.warning(
        "QUALITY_WEIGHTS do not sum to 1.0 (got %.6f) — auto-normalizing. "
        "Please fix the weights explicitly.", _total_w
    )
    QUALITY_WEIGHTS = {k: round(v / _total_w, 6) for k, v in QUALITY_WEIGHTS.items()}

assert abs(sum(QUALITY_WEIGHTS.values()) - 1.0) < 1e-4, \
    "QUALITY_WEIGHTS must sum to 1.0"


# ── Main entry point ───────────────────────────────────────────────────────────

def analyze_resume_quality(resume_text: str, pdf_bytes: Optional[bytes] = None) -> Dict:
    """
    Run all quality evaluators and return a structured quality report
    with an overall composite score (0.0 – 1.0).
    """
    text_lower = resume_text.lower()

    # Determine fresher status for readability threshold
    exp_kws       = ["work experience", "professional experience",
                     "employment history", "job title"]
    is_experienced = any(kw in text_lower for kw in exp_kws)

    length_result = check_resume_length(resume_text, pdf_bytes)
    is_fresher    = length_result.get("is_fresher", not is_experienced)

    details = {
        "section_completeness": check_section_completeness(text_lower),
        "ats_compatibility":    check_ats_compatibility(resume_text, pdf_bytes),
        "chronological_order":  check_chronological_order(resume_text),
        "achievements_quality": check_achievements_quality(resume_text),
        "contact_info":         check_contact_info(resume_text),
        "readability":          check_readability(resume_text, is_fresher=is_fresher),
        "resume_length":        length_result,
        "project_quality":      check_project_quality(text_lower),
        "keyword_density":      check_keyword_density(resume_text),
        "formatting":           check_formatting(pdf_bytes),
    }

    scores = {dim: details[dim]["score"] for dim in details}

    overall = sum(
        scores[dim] * QUALITY_WEIGHTS.get(dim, 0)
        for dim in scores
    )

    return {
        "overall": round(overall, 4),
        "scores":  {k: round(v, 4) for k, v in scores.items()},
        "details": details,
    }
