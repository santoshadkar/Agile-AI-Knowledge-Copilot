"""LLM model factories + fallback-chain helper, shared by the routing and
generation nodes.

Things learned by actually calling these APIs while building this (not
assumed from docs):

1. Gemini version-pinned model names (gemini-3.7-flash, gemini-3.5-flash-lite)
   returned transient 503/504 errors during testing; the gemini-*-latest
   aliases didn't, and they track Google's current release instead of a
   pinned version that can get deprecated -- used throughout.
2. ChatGoogleGenerativeAI's .content is not reliably a plain string -- it
   can come back as a list of content-part dicts (e.g. [{"type": "text",
   "text": "...", "extras": {...}}]). extract_text() normalizes that
   (ChatGroq's .content is a plain string, so this is a no-op there).
3. Deploying and testing against the real production site turned up a
   broad, intermittent "high demand" 503 affecting multiple Gemini flash
   models AT THE SAME TIME (not one model specifically overloaded --
   the whole flash tier short on capacity for a stretch). A model that
   failed at one moment succeeded ~19s later on a fresh attempt, which is
   what justified bumping retries. But retries alone can't help if Google's
   infrastructure itself is degraded across the board, which is what
   motivated adding Groq (openai/gpt-oss-120b) as a third tier: it runs on
   entirely separate infrastructure, so a Gemini-side capacity issue
   doesn't touch it at all.

Every generation call goes through a fallback CHAIN now, not just a single
fallback pair: gemini-flash-latest -> gemini-flash-lite-latest -> Groq.
"""

import logging
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from app.config import get_settings

GENERATION_MODEL = "gemini-flash-latest"
GENERATION_FALLBACK_MODEL = "gemini-flash-lite-latest"
ROUTING_MODEL = "gemini-flash-lite-latest"  # cheap classification task, doesn't need the larger model
GROQ_MODEL = "openai/gpt-oss-120b"  # confirmed available via a live models.list() call -- Groq's lineup
# has moved on from the llama-3.x names common in older docs/tutorials.

# Bumped from 2 to 4 after live testing during deployment turned up the
# intermittent Gemini capacity issue described above.
_GEMINI_TIMEOUT_SECONDS = 30
_GEMINI_MAX_RETRIES = 4
_GROQ_TIMEOUT_SECONDS = 30
_GROQ_MAX_RETRIES = 2

logger = logging.getLogger(__name__)


@lru_cache
def _build_gemini_llm(model: str) -> ChatGoogleGenerativeAI:
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.gemini_api_key,
        timeout=_GEMINI_TIMEOUT_SECONDS,
        max_retries=_GEMINI_MAX_RETRIES,
    )


@lru_cache
def get_groq_llm() -> ChatGroq:
    settings = get_settings()
    return ChatGroq(
        model_name=GROQ_MODEL,
        groq_api_key=settings.groq_api_key,
        request_timeout=_GROQ_TIMEOUT_SECONDS,
        max_retries=_GROQ_MAX_RETRIES,
    )


def get_generation_llm() -> ChatGoogleGenerativeAI:
    return _build_gemini_llm(GENERATION_MODEL)


def get_generation_fallback_llm() -> ChatGoogleGenerativeAI:
    return _build_gemini_llm(GENERATION_FALLBACK_MODEL)


def get_routing_llm() -> ChatGoogleGenerativeAI:
    return _build_gemini_llm(ROUTING_MODEL)


def _model_label(model: BaseChatModel) -> str:
    return getattr(model, "model", None) or getattr(model, "model_name", None) or type(model).__name__


def invoke_with_fallback(messages: list, *models: BaseChatModel) -> str:
    """Try each model in order, returning the first success. Raises
    RuntimeError with every model's failure reason if all of them fail.
    Returns extracted text directly since every caller wants that, not
    the raw AIMessage."""
    if not models:
        raise ValueError("invoke_with_fallback needs at least one model")

    failures: list[str] = []
    for model in models:
        try:
            return extract_text(model.invoke(messages))
        except Exception as exc:
            label = _model_label(model)
            logger.warning("Model %s failed (%s)", label, exc)
            failures.append(f"{label}: {exc}")

    raise RuntimeError(f"All {len(models)} model(s) failed. " + " | ".join(failures))


def extract_text(message) -> str:
    """Normalize a chat model's .content, which can be a plain string
    (Groq) or a list of content-part dicts (Gemini, sometimes)."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content)
