"""Gemini model factory + fallback helper, shared by the routing and
generation nodes.

Two things learned by actually calling the API while building this (not
assumed from docs):

1. Version-pinned model names (gemini-3.7-flash, gemini-3.5-flash-lite)
   returned transient 503/504 errors during testing; the gemini-*-latest
   aliases didn't, and they track Google's current release instead of a
   pinned version that can get deprecated -- used throughout.
2. ChatGoogleGenerativeAI's .content is not reliably a plain string -- it
   can come back as a list of content-part dicts (e.g. [{"type": "text",
   "text": "...", "extras": {...}}]). extract_text() normalizes that.

Per this project's experience with Gemini's free tier being tightly
rate-limited per model, every LLM call in the graph goes through a primary
model with a same-tier fallback rather than betting on a single model.
"""

import logging
from functools import lru_cache

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings

GENERATION_MODEL = "gemini-flash-latest"
GENERATION_FALLBACK_MODEL = "gemini-flash-lite-latest"
ROUTING_MODEL = "gemini-flash-lite-latest"  # cheap classification task, doesn't need the larger model

_TIMEOUT_SECONDS = 30
_MAX_RETRIES = 2

logger = logging.getLogger(__name__)


@lru_cache
def _build_llm(model: str) -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.gemini_api_key,
        timeout=_TIMEOUT_SECONDS,
        max_retries=_MAX_RETRIES,
    )


def get_generation_llm() -> ChatGoogleGenerativeAI:
    return _build_llm(GENERATION_MODEL)


def get_generation_fallback_llm() -> ChatGoogleGenerativeAI:
    return _build_llm(GENERATION_FALLBACK_MODEL)


def get_routing_llm() -> ChatGoogleGenerativeAI:
    return _build_llm(ROUTING_MODEL)


def invoke_with_fallback(messages: list, *, primary: ChatGoogleGenerativeAI, fallback: ChatGoogleGenerativeAI) -> str:
    """Invoke primary, falling back to a second model on any error
    (rate limit, timeout, transient 5xx -- all observed during testing).
    Returns extracted text directly since every caller wants that, not
    the raw AIMessage."""
    try:
        return extract_text(primary.invoke(messages))
    except Exception as primary_error:
        logger.warning("Primary model %s failed (%s), falling back to %s", primary.model, primary_error, fallback.model)
        try:
            return extract_text(fallback.invoke(messages))
        except Exception as fallback_error:
            raise RuntimeError(
                f"Both Gemini models failed. Primary ({primary.model}): {primary_error}. "
                f"Fallback ({fallback.model}): {fallback_error}."
            ) from fallback_error


def extract_text(message) -> str:
    """Normalize ChatGoogleGenerativeAI's .content, which can be a plain
    string or a list of content-part dicts depending on the response."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content)
