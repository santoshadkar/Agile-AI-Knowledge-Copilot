"""POST /ingest -- upload a PDF/DOCX/Markdown file, tag its domain, and run
it through the ingestion pipeline (build step 2).

The uploaded file only ever touches a TemporaryDirectory for the duration
of one request, never a persistent path -- consistent with Render's free
tier having no persistent disk. It's deleted the moment the request
finishes regardless of success or failure.
"""

import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.ingestion.loaders import SUPPORTED_EXTENSIONS
from app.ingestion.pipeline import ConfidentialityFlagError, ingest_file

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


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
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
            result = ingest_file(tmp_path, domain=domain, force=force)
        except ConfidentialityFlagError as exc:
            raise HTTPException(
                status_code=422,
                detail={"message": str(exc), "reasons": exc.reasons, "source": exc.source},
            ) from exc

    return IngestResponse(
        source=result.source,
        domain=result.domain,
        chunk_count=result.chunk_count,
        confidentiality_flags=result.confidentiality_flags,
    )
