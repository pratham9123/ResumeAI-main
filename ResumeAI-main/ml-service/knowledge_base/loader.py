"""File-system loader for the curated resume-guidance knowledge base."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .schema import KnowledgeChunk, KnowledgeValidationError


logger = logging.getLogger(__name__)
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True, slots=True)
class KnowledgeLoadIssue:
    """A malformed file or chunk skipped during loading."""

    file: str
    message: str
    entry_index: int | None = None

    def __str__(self) -> str:
        location = self.file
        if self.entry_index is not None:
            location += f"[chunks][{self.entry_index}]"
        return f"{location}: {self.message}"


@dataclass(slots=True)
class KnowledgeLoadResult:
    """Detailed result used by validation commands and diagnostics."""

    chunks: list[KnowledgeChunk] = field(default_factory=list)
    issues: list[KnowledgeLoadIssue] = field(default_factory=list)
    files_scanned: int = 0
    entries_scanned: int = 0

    @property
    def normalized_chunks(self) -> list[dict[str, Any]]:
        return [chunk.to_dict() for chunk in self.chunks]


def _extract_entries(document: Any) -> list[Any]:
    if isinstance(document, list):
        return document
    if isinstance(document, dict) and isinstance(document.get("chunks"), list):
        return document["chunks"]
    raise KnowledgeValidationError(
        "file root must be a JSON array or an object containing a 'chunks' array"
    )


def load_knowledge_base(data_dir: str | Path | None = None) -> KnowledgeLoadResult:
    """
    Read and validate every JSON file in a knowledge directory.

    Invalid JSON, malformed entries, and later occurrences of duplicate IDs are
    reported in ``issues`` and skipped. Files are processed by name and entries
    retain file order, making the normalized result deterministic.
    """

    root = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    result = KnowledgeLoadResult()

    if not root.exists() or not root.is_dir():
        result.issues.append(
            KnowledgeLoadIssue(str(root), "knowledge directory does not exist")
        )
        return result

    seen_ids: dict[str, str] = {}
    json_files = sorted(path for path in root.glob("*.json") if path.is_file())

    for path in json_files:
        result.files_scanned += 1
        try:
            with path.open("r", encoding="utf-8") as handle:
                entries = _extract_entries(json.load(handle))
        except (OSError, json.JSONDecodeError, KnowledgeValidationError) as exc:
            result.issues.append(KnowledgeLoadIssue(str(path), str(exc)))
            continue

        for index, payload in enumerate(entries):
            result.entries_scanned += 1
            try:
                chunk = KnowledgeChunk.from_dict(payload)
            except KnowledgeValidationError as exc:
                result.issues.append(KnowledgeLoadIssue(str(path), str(exc), index))
                continue

            if chunk.id in seen_ids:
                result.issues.append(
                    KnowledgeLoadIssue(
                        str(path),
                        f"duplicate id '{chunk.id}' (first defined in {seen_ids[chunk.id]})",
                        index,
                    )
                )
                continue

            seen_ids[chunk.id] = str(path)
            result.chunks.append(chunk)

    return result


def load_knowledge_chunks(
    data_dir: str | Path | None = None,
    *,
    strict: bool = False,
) -> list[dict[str, Any]]:
    """Return normalized chunks, optionally failing if any entry was skipped."""

    result = load_knowledge_base(data_dir)
    if result.issues:
        messages = "\n".join(str(issue) for issue in result.issues)
        if strict:
            raise KnowledgeValidationError(
                f"knowledge base contains {len(result.issues)} issue(s):\n{messages}"
            )
        for issue in result.issues:
            logger.warning("Skipping knowledge-base content: %s", issue)

    return result.normalized_chunks
