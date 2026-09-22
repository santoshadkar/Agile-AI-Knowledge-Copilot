"""Walk backend/sample_docs/<domain>/* and ingest every file into Qdrant.

Run from the backend/ directory (so the `app` package resolves) with the
venv active and a real .env in place:

    python scripts/ingest_sample_docs.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.loaders import SUPPORTED_EXTENSIONS
from app.ingestion.pipeline import ConfidentialityFlagError, ingest_file

SAMPLE_DOCS_DIR = Path(__file__).resolve().parent.parent / "sample_docs"


def main() -> None:
    if not SAMPLE_DOCS_DIR.exists():
        raise SystemExit(f"No sample_docs directory at {SAMPLE_DOCS_DIR}")

    total_chunks = 0
    total_files = 0

    for domain_dir in sorted(SAMPLE_DOCS_DIR.iterdir()):
        if not domain_dir.is_dir():
            continue
        domain = domain_dir.name

        for path in sorted(domain_dir.iterdir()):
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            try:
                result = ingest_file(path, domain=domain)
            except ConfidentialityFlagError as exc:
                print(f"SKIPPED  {domain}/{path.name}: {exc}")
                continue

            total_files += 1
            total_chunks += result.chunk_count
            print(f"OK       {domain}/{path.name}: {result.chunk_count} chunks")

    print(f"\nIngested {total_files} file(s), {total_chunks} chunk(s) total.")


if __name__ == "__main__":
    main()
