"""Validation and normalization model for resume-guidance chunks."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping


ALLOWED_ROLES = frozenset(
    {
        "software_engineer",
        "backend_developer",
        "frontend_developer",
        "fullstack_developer",
        "data_analyst",
        "machine_learning_engineer",
        "general",
    }
)

REQUIRED_FIELDS = frozenset({"id", "role", "category", "title", "text", "source", "tags"})
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_CATEGORY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class KnowledgeValidationError(ValueError):
    """Raised when a knowledge chunk does not satisfy the data contract."""


def _normalized_text(value: Any, field: str, minimum_length: int = 1) -> str:
    if not isinstance(value, str):
        raise KnowledgeValidationError(f"'{field}' must be a string")
    normalized = " ".join(value.split())
    if len(normalized) < minimum_length:
        raise KnowledgeValidationError(
            f"'{field}' must contain at least {minimum_length} characters"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    """A validated, normalized unit of retrievable resume guidance."""

    id: str
    role: str
    category: str
    title: str
    text: str
    source: str
    tags: tuple[str, ...]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "KnowledgeChunk":
        if not isinstance(payload, Mapping):
            raise KnowledgeValidationError("chunk must be a JSON object")

        missing = sorted(REQUIRED_FIELDS - payload.keys())
        if missing:
            raise KnowledgeValidationError(
                f"missing required field(s): {', '.join(missing)}"
            )

        unknown = sorted(payload.keys() - REQUIRED_FIELDS)
        if unknown:
            raise KnowledgeValidationError(
                f"unknown field(s): {', '.join(unknown)}"
            )

        chunk_id = _normalized_text(payload["id"], "id").lower()
        if not _IDENTIFIER_PATTERN.fullmatch(chunk_id):
            raise KnowledgeValidationError(
                "'id' must use lowercase letters, numbers, dots, underscores, or hyphens"
            )

        role = _normalized_text(payload["role"], "role").lower()
        if role not in ALLOWED_ROLES:
            allowed = ", ".join(sorted(ALLOWED_ROLES))
            raise KnowledgeValidationError(
                f"unsupported role '{role}'; expected one of: {allowed}"
            )

        category = _normalized_text(payload["category"], "category").lower()
        if not _CATEGORY_PATTERN.fullmatch(category):
            raise KnowledgeValidationError("'category' must be a snake_case identifier")

        title = _normalized_text(payload["title"], "title", minimum_length=3)
        text = _normalized_text(payload["text"], "text", minimum_length=40)
        source = _normalized_text(payload["source"], "source", minimum_length=3)

        raw_tags = payload["tags"]
        if not isinstance(raw_tags, list) or not raw_tags:
            raise KnowledgeValidationError("'tags' must be a non-empty JSON array")

        normalized_tags = []
        for index, tag in enumerate(raw_tags):
            normalized = _normalized_text(tag, f"tags[{index}]").lower()
            normalized = re.sub(r"[^a-z0-9+#.-]+", "_", normalized).strip("_")
            if not normalized:
                raise KnowledgeValidationError(f"'tags[{index}]' is invalid")
            if normalized not in normalized_tags:
                normalized_tags.append(normalized)

        return cls(
            id=chunk_id,
            role=role,
            category=category,
            title=title,
            text=text,
            source=source,
            tags=tuple(normalized_tags),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable normalized representation."""
        result = asdict(self)
        result["tags"] = list(self.tags)
        return result
