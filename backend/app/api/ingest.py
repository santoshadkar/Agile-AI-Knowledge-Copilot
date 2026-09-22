from fastapi import APIRouter

router = APIRouter()

# Wired up in build step 4, once the ingestion pipeline (step 2) exists.
# Will accept a file upload (PDF/DOCX/MD) + a domain tag, then chunk, embed, and upsert to Qdrant.
