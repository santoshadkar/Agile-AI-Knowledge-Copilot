"""End-to-end ingestion: load -> safety-scan -> chunk -> embed -> upsert.

Used by both the CLI (scripts/ingest_sample_docs.py) and the POST /ingest
API endpoint -- this module has no FastAPI or CLI concerns in it, just the
pipeline itself.

Split into two phases (prepare_ingestion / commit_ingestion) rather than
one synchronous call, because of a real failure observed in production:
a large document (~80KB, ~40 sections) took long enough to embed that
Render's free-tier proxy killed the connection with a 502 after ~67
seconds, before our own code ever got to respond -- which surfaced to the
browser as a generic "Failed to fetch" with no useful detail. The fix
isn't "make embedding faster" (there's a hard floor on API latency), it's
"don't hold the HTTP request open for the slow part." prepare_ingestion
(load + safety-scan + chunk) is fast, CPU-only, and safe to run inline;
commit_ingestion (the actual embed + upsert calls) is what the API layer
now runs via FastAPI's BackgroundTasks *after* responding.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.documents import Document

from app.ingestion.chunking import chunk_markdown
from app.ingestion.loaders import load_as_markdown
from app.ingestion.safety import scan_for_confidentiality_markers
from app.resilience import voyage_retry
from app.vectorstore.qdrant_client import delete_by_source, get_vector_store

VALID_DOMAINS = {"agile-coaching", "claude-certification"}

logger = logging.getLogger(__name__)


@voyage_retry
def _add_documents_with_backoff(vector_store, chunks) -> None:
    vector_store.add_documents(chunks)


@dataclass
class IngestResult:
    source: str
    domain: str
    chunk_count: int
    confidentiality_flags: list[str] = field(default_factory=list)
    skipped: bool = False


@dataclass
class PreparedIngestion:
    source: str
    domain: str
    chunks: list[Document]
    confidentiality_flags: list[str] = field(default_factory=list)


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


def prepare_ingestion(path: Path, *, domain: str, force: bool = False) -> PreparedIngestion:
    """The fast part: load the file, run the confidentiality scan, chunk
    the text. No network calls -- safe to run inline in a request handler."""
    if domain not in VALID_DOMAINS:
        raise ValueError(f"domain must be one of {sorted(VALID_DOMAINS)}, got '{domain}'")

    markdown_text = load_as_markdown(path)

    flags = scan_for_confidentiality_markers(markdown_text, path.name)
    if flags and not force:
        raise ConfidentialityFlagError(path.name, flags)

    chunks = chunk_markdown(markdown_text, source=path.name, domain=domain)

    return PreparedIngestion(source=path.name, domain=domain, chunks=chunks, confidentiality_flags=flags)


def commit_ingestion(prepared: PreparedIngestion) -> None:
    """The slow part: embed + upsert. Meant to be handed to
    FastAPI's BackgroundTasks (runs in a worker thread, per Starlette's
    BackgroundTask -- confirmed by reading its source before relying on
    this -- so it doesn't block the event loop for other requests while
    it runs)."""
    try:
        delete_by_source(domain=prepared.domain, source=prepared.source)
        vector_store = get_vector_store()
        _add_documents_with_backoff(vector_store, prepared.chunks)
    except Exception:
        # Nothing left to respond to at this point -- the HTTP response
        # already went out. Log loudly so a failure here is at least
        # visible in server logs instead of silently vanishing.
        logger.exception("Background ingestion failed for %s (%s)", prepared.source, prepared.domain)
        raise


def ingest_file(path: Path, *, domain: str, force: bool = False) -> IngestResult:
    """Synchronous convenience wrapper (prepare + commit in one call) for
    the CLI script and tests, where there's no HTTP request timeout to
    worry about. The API endpoint calls prepare_ingestion/commit_ingestion
    separately instead -- see app/api/ingest.py."""
    prepared = prepare_ingestion(path, domain=domain, force=force)
    commit_ingestion(prepared)
    return IngestResult(
        source=prepared.source,
        domain=prepared.domain,
        chunk_count=len(prepared.chunks),
        confidentiality_flags=prepared.confidentiality_flags,
    )
