import re
import logging
from typing import Dict, List
from modules.resume_quality import SECTION_KEYWORDS, ACTION_VERBS, QUANTIFICATION_PATTERNS

logger = logging.getLogger(__name__)

def split_into_sections(resume_text: str) -> Dict[str, str]:
    lines = resume_text.split('\n')
    sections = {
        "education": "",
        "experience": "",
        "projects": "",
        "skills": "",
        "achievements": "",
        "summary": ""
    }
    
    current_section = None
    all_kws = {s: SECTION_KEYWORDS[s] for s in sections.keys() if s in SECTION_KEYWORDS}
    
    for line in lines:
        stripped = line.strip()
        if 0 < len(stripped) <= 60 and re.search(r'[a-z]', line.lower()):
            line_lower = stripped.lower()
            matched_section = None
            for sec, kws in all_kws.items():
                if any(kw in line_lower for kw in kws):
                    matched_section = sec
                    break
            
            if matched_section:
                current_section = matched_section
                continue # skip the header line itself
                
        if current_section:
            sections[current_section] += line + "\n"
            
    return sections

def score_experience(text: str) -> int:
    if not text.strip(): return 0
    text_lower = text.lower()
    
    found_verbs = [v for v in ACTION_VERBS if re.search(r"\b" + v + r"\b", text_lower)]
    verb_score = min(len(found_verbs) / 4, 1.0)
    
    quant_matches = []
    for pattern in QUANTIFICATION_PATTERNS:
        quant_matches.extend(re.findall(pattern, text, re.IGNORECASE))
    quant_score = min(len(quant_matches) / 2, 1.0)
    
    score = (verb_score * 0.6 + quant_score * 0.4) * 10
    return max(3, round(score)) # Baseline 3 if exists but poor

def score_projects(text: str) -> int:
    if not text.strip(): return 0
    text_lower = text.lower()
    score = 4 # base score for having projects
    
    if "github" in text_lower: score += 2
    if any(p in text_lower for p in ["built with", "tech stack", "technologies"]): score += 2
    
    impact_words = ["users", "reduced", "improved", "optimized", "live", "demo", "deployed"]
    if any(w in text_lower for w in impact_words): score += 2
    
    return min(10, score)

def score_skills(text: str) -> int:
    if not text.strip(): return 0
    words = len(re.findall(r"\b\w+\b", text))
    if words > 10: return 10
    if words > 5: return 8
    return 5

def score_education(text: str) -> int:
    if not text.strip(): return 0
    score = 6
    if re.search(r"\b(20\d{2}|19\d{2})\b", text): score += 2
    if re.search(r"\b(gpa|cgpa|marks|%)\b", text.lower()): score += 2
    return min(10, score)

def analyze_sections(resume_text: str) -> Dict[str, int]:
    """
    Splits the resume into chunks and returns a score out of 10 for each.
    """
    sections = split_into_sections(resume_text)
    scores = {}
    
    if sections["experience"].strip():
        scores["Experience"] = score_experience(sections["experience"])
    if sections["projects"].strip():
        scores["Projects"] = score_projects(sections["projects"])
    if sections["skills"].strip():
        scores["Skills"] = score_skills(sections["skills"])
    if sections["education"].strip():
        scores["Education"] = score_education(sections["education"])
        
    return scores
