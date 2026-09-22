from fastapi import APIRouter

router = APIRouter()

# Wired up in build step 4, once the LangGraph RAG graph (step 3) exists.
# Will accept {"message": str, "domain": "agile-coaching" | "claude-certification" | "both"}
# and stream a cited answer back.
