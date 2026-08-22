"""Local command-line smoke test for ResumeAI knowledge retrieval."""

from __future__ import annotations

import argparse

from .query_builder import RetrievalQueryBuilder
from .retriever import RetrievalError, get_retriever
from .schema import ALLOWED_ROLES


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a sample ResumeAI retrieval query")
    parser.add_argument("--role", choices=sorted(ALLOWED_ROLES), default="software_engineer")
    parser.add_argument("--query", help="explicit concise query; otherwise a sample is built")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.25)
    args = parser.parse_args()

    query = args.query or RetrievalQueryBuilder().build(
        target_role=args.role,
        missing_skills=["Java", "unit testing", "backend deployment"],
        weak_resume_sections=["projects"],
        resume_quality_scores={"achievements_quality": 0.42},
        experience_level="entry level",
        project_weaknesses=["project bullets lack measurable impact"],
    )

    print(f"Query: {query}\n")
    try:
        results = get_retriever().retrieve(
            query,
            target_role=args.role,
            top_k=args.top_k,
            minimum_similarity=args.threshold,
        )
    except RetrievalError as exc:
        print(f"Retrieval failed: {exc}")
        return 1

    if not results:
        print("No guidance matched the requested filters and threshold.")
        return 0

    for result in results:
        print(
            f"#{result['rank']}  score={result['similarity_score']:.4f}  "
            f"[{result['role']}/{result['category']}]"
        )
        print(f"{result['title']} ({result['id']})")
        print(f"{result['text']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
