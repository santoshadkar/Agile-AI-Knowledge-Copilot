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
   the whole flash tier short on capacity for a stretch). This first
   justified bumping max_retries 2 -> 4 -- which then caused a *real*
   regression, a single /chat request measured at 155 seconds end to end.
   Root cause: ChatGoogleGenerativeAI's max_retries wraps ANOTHER retry
   layer inside the underlying google-genai SDK itself (tenacity,
   exponential backoff up to 60s, up to 5 attempts by default) -- our
   "4 retries" was compounding against that hidden layer, not adding to
   it linearly. Confirmed by direct measurement: max_retries=0 makes a
   genuine failure surface in ~4s; higher values blow up non-linearly.
4. The actual fix isn't "tune retries correctly" -- it's that per-model
   retries are the wrong tool once you have a real multi-provider fallback
   CHAIN (gemini-flash-latest -> gemini-flash-lite-latest -> Groq, added
   after discovering Gemini's daily per-model quota). Retrying a struggling
   model just delays reaching a model that isn't struggling. Each model
   here gets ONE attempt (max_retries=0) with a short timeout; the chain
   itself is the redundancy, not internal retries within a single tier.
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

# max_retries=0 disables both the LangChain-level retry AND the hidden
# internal google-genai SDK retry it wraps -- confirmed by direct
# measurement (see point 3 above). One fast attempt per tier; the 3-model
# chain is what provides redundancy, not retrying within a tier.
_GEMINI_TIMEOUT_SECONDS = 15
_GEMINI_MAX_RETRIES = 0
_GROQ_TIMEOUT_SECONDS = 15
_GROQ_MAX_RETRIES = 0

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
