"""
semantic_matcher.py
-------------------
Semantic similarity between resume and job description.

Improvements over v1:
- Text extraction uses beginning + end strategy (1500 chars each) so
  certifications/projects at the bottom of the resume are included.
- Embedding results are cached via functools.lru_cache on a text hash,
  so repeated submissions of the same resume don't re-encode.
- TF-IDF fallback replaced with CountVectorizer + cosine (honest pure-TF),
  since IDF is meaningless when fitting on only 2 documents.
- SEMANTIC_MODEL_SHARED env var: set to "0" to disable the global model
  singleton and use TF instead (for multi-worker gunicorn deployments where
  each worker loading a 90MB model causes RAM pressure).
"""

import os
import logging
import functools
import numpy as np

from modules.embedding_service import (
    DEFAULT_MODEL_NAME,
    EmbeddingError,
    cached_encode_text,
    get_shared_sentence_transformer,
    sha256_text,
)

logger = logging.getLogger(__name__)

# Set SEMANTIC_MODEL_SHARED=0 in .env to force TF-IDF (multi-worker gunicorn)
_USE_TRANSFORMER = os.getenv("SEMANTIC_MODEL_SHARED", "1") != "0"


def _get_model():
    if not _USE_TRANSFORMER:
        return "tfidf"
    try:
        return get_shared_sentence_transformer(DEFAULT_MODEL_NAME)
    except EmbeddingError:
        logger.warning(
            "sentence-transformers not installed. Falling back to TF similarity."
        )
        return "tfidf"


# ── Text sampling strategy ─────────────────────────────────────────────────────

def _sample_text(text: str, max_chars: int = 3000) -> str:
    """
    Return up to max_chars characters from the text using a
    beginning + end strategy so content at the bottom (certifications,
    additional projects) is included rather than silently dropped.
    """
    if len(text) <= max_chars:
        return text
    half  = max_chars // 2
    start = text[:half]
    end   = text[-half:]
    return start + "\n...\n" + end


# ── Cached embedding helper ────────────────────────────────────────────────────

@functools.lru_cache(maxsize=64)
def _cached_encode(text_hash: str, text: str):
    """
    Encode text to embedding vector, cached by SHA-256 hash of the text.
    The hash is passed as the first arg so lru_cache can use it as the key
    without hashing the (potentially large) text string itself each time.
    """
    if _get_model() == "tfidf":
        return None
    return cached_encode_text(text_hash, text, DEFAULT_MODEL_NAME)


def _text_hash(text: str) -> str:
    return sha256_text(text)


# ── Similarity helpers ─────────────────────────────────────────────────────────

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0


def _tf_similarity(text1: str, text2: str) -> float:
    """
    Pure term-frequency cosine similarity (no IDF weighting).

    IDF is meaningless when fitting on only 2 documents — all terms would get
    the same IDF weight, so we use raw TF counts instead for an honest result.
    """
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as sk_cosine
    try:
        vec   = CountVectorizer(stop_words="english", max_features=5000)
        counts = vec.fit_transform([text1, text2])
        return float(sk_cosine(counts[0], counts[1])[0][0])
    except Exception as e:
        logger.warning("TF similarity failed: %s", e)
        return 0.0


# ── Public API ─────────────────────────────────────────────────────────────────

def compute_similarity(resume_text: str, job_description: str) -> float:
    """
    Compute semantic similarity between resume and JD.
    Uses sentence-transformers when available, falls back to TF cosine.
    """
    resume_sampled = _sample_text(resume_text, max_chars=3000)
    jd_sampled     = _sample_text(job_description, max_chars=2000)

    model = _get_model()

    if model == "tfidf":
        return _tf_similarity(resume_sampled, jd_sampled)

    # Use cached embeddings
    r_hash = _text_hash(resume_sampled)
    j_hash = _text_hash(jd_sampled)

    r_emb = _cached_encode(r_hash, resume_sampled)
    j_emb = _cached_encode(j_hash, jd_sampled)

    if r_emb is None or j_emb is None:
        return _tf_similarity(resume_sampled, jd_sampled)

    score = _cosine(r_emb, j_emb)
    return float(min(max(score, 0.0), 1.0))
