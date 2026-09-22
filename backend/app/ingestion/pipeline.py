"""End-to-end ingestion: load -> safety-scan -> chunk -> embed -> upsert.

Used by both the CLI (scripts/ingest_sample_docs.py) and, in build step 4,
the POST /ingest API endpoint -- this module has no FastAPI or CLI concerns
in it, just the pipeline itself.
"""

from dataclasses import dataclass, field
from pathlib import Path

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from voyageai.error import RateLimitError

from app.ingestion.chunking import chunk_markdown
from app.ingestion.loaders import load_as_markdown
from app.ingestion.safety import scan_for_confidentiality_markers
from app.vectorstore.qdrant_client import delete_by_source, get_vector_store

VALID_DOMAINS = {"agile-coaching", "claude-certification"}

# Voyage AI caps accounts with no payment method on file at 3 requests/minute
# (the 200M free tokens still apply -- this only throttles request rate).
# Backs off hard enough to ride that out rather than requiring a card on file
# just to prove the pipeline works.
@retry(
    retry=retry_if_exception_type(RateLimitError),
    wait=wait_exponential(multiplier=5, min=5, max=60),
    stop=stop_after_attempt(6),
    reraise=True,
)
def _add_documents_with_backoff(vector_store, chunks) -> None:
    vector_store.add_documents(chunks)


@dataclass
class IngestResult:
    source: str
    domain: str
    chunk_count: int
    confidentiality_flags: list[str] = field(default_factory=list)
    skipped: bool = False


class ConfidentialityFlagError(Exception):
    """Raised when a document trips the confidentiality guard and the caller
    hasn't explicitly overridden it."""

    def __init__(self, source: str, reasons: list[str]):
        self.source = source
        self.reasons = reasons
        super().__init__(
            f"'{source}' looks like it may be proprietary/confidential: {'; '.join(reasons)}. "
            f"Pass force=True to ingest anyway."
        )


def ingest_file(path: Path, *, domain: str, force: bool = False) -> IngestResult:
    if domain not in VALID_DOMAINS:
        raise ValueError(f"domain must be one of {sorted(VALID_DOMAINS)}, got '{domain}'")

    markdown_text = load_as_markdown(path)

    flags = scan_for_confidentiality_markers(markdown_text, path.name)
    if flags and not force:
        raise ConfidentialityFlagError(path.name, flags)

    chunks = chunk_markdown(markdown_text, source=path.name, domain=domain)

    delete_by_source(domain=domain, source=path.name)
    vector_store = get_vector_store()
    _add_documents_with_backoff(vector_store, chunks)

    return IngestResult(
        source=path.name,
        domain=domain,
        chunk_count=len(chunks),
        confidentiality_flags=flags,
    )
