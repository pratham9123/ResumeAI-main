"""Curated resume-writing knowledge base for the ResumeAI ML service."""

from .loader import (
    KnowledgeLoadIssue,
    KnowledgeLoadResult,
    load_knowledge_base,
    load_knowledge_chunks,
)
from .schema import ALLOWED_ROLES, KnowledgeChunk, KnowledgeValidationError

__all__ = [
    "ALLOWED_ROLES",
    "KnowledgeChunk",
    "KnowledgeLoadIssue",
    "KnowledgeLoadResult",
    "KnowledgeValidationError",
    "load_knowledge_base",
    "load_knowledge_chunks",
]
