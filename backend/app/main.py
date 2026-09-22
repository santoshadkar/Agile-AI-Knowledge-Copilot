from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, health, ingest
from app.config import get_settings

app = FastAPI(title="Agile & AI Knowledge Copilot")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(ingest.router)
