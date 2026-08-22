"""Command-line validation for the ResumeAI knowledge corpus."""

from __future__ import annotations

import argparse
from pathlib import Path

from .loader import DEFAULT_DATA_DIR, load_knowledge_base


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ResumeAI knowledge JSON files")
    parser.add_argument(
        "data_dir",
        nargs="?",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="directory containing knowledge JSON files",
    )
    args = parser.parse_args()

    result = load_knowledge_base(args.data_dir)
    print(
        f"Scanned {result.files_scanned} file(s) and {result.entries_scanned} entry/entries; "
        f"loaded {len(result.chunks)} valid chunk(s)."
    )

    if result.issues:
        print(f"Found {len(result.issues)} issue(s):")
        for issue in result.issues:
            print(f"- {issue}")
        return 1

    print("Knowledge base is valid: no malformed entries or duplicate IDs found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
