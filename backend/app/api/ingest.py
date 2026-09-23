"""POST /ingest -- upload a PDF/DOCX/Markdown file, tag its domain, and run
it through the ingestion pipeline (build step 2).

The uploaded file only ever touches a TemporaryDirectory for the duration
of one request, never a persistent path -- consistent with Render's free
tier having no persistent disk. It's deleted the moment the request
finishes regardless of success or failure.

Responds as soon as the fast part (load, safety-scan, chunk) is done and
runs the slow part (embed + upsert) as a background task, rather than
blocking the whole request on it. This isn't a style preference -- a real
document (~80KB, ~40 sections) reproducibly triggered a 502 from Render's
free-tier proxy after ~67 seconds when this endpoint was fully synchronous,
which surfaced in the browser as a generic "Failed to fetch" with no
useful detail (see the pipeline.py module docstring for the full story).
"""

import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.ingestion.loaders import SUPPORTED_EXTENSIONS
from app.ingestion.pipeline import ConfidentialityFlagError, commit_ingestion, prepare_ingestion

router = APIRouter()

# 10MB is generous for text-heavy PDF/DOCX/MD source docs and bounds memory
# use -- the whole file is read into memory (await file.read()) before
# touching disk, which matters on Render's free-tier RAM ceiling.
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

IngestDomain = Literal["agile-coaching", "claude-certification"]


class IngestResponse(BaseModel):
    source: str
    domain: str
    chunk_count: int
    confidentiality_flags: list[str]
    status: Literal["processing"] = "processing"


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    domain: IngestDomain = Form(...),
    force: bool = Form(False),
) -> IngestResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB)",
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / file.filename
        tmp_path.write_bytes(contents)

        try:
            prepared = prepare_ingestion(tmp_path, domain=domain, force=force)
        except ConfidentialityFlagError as exc:
            raise HTTPException(
                status_code=422,
                detail={"message": str(exc), "reasons": exc.reasons, "source": exc.source},
            ) from exc
        # prepared.chunks are already-extracted Document objects in memory,
        # not dependent on tmp_path -- safe to hand to a background task
        # that runs after this TemporaryDirectory is cleaned up.

    background_tasks.add_task(commit_ingestion, prepared)

    return IngestResponse(
        source=prepared.source,
        domain=prepared.domain,
        chunk_count=len(prepared.chunks),
        confidentiality_flags=prepared.confidentiality_flags,
    )
