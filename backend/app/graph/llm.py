"""LLM model factories + fallback-chain helper, shared by the routing and
generation nodes.

History (kept because each entry is a real bug found by testing, not
hypothetical, and the reasoning matters for whoever touches this next):

1. Originally Gemini-only (gemini-flash-latest -> gemini-flash-lite-latest).
   Deploying and testing against the real production site turned up a
   broad, intermittent "high demand" 503 affecting multiple Gemini flash
   models AT THE SAME TIME -- not one model overloaded, the whole flash
   tier short on capacity for a stretch.
2. Bumping max_retries 2 -> 4 to ride that out caused a real regression:
   a single /chat request measured at 155 seconds. Root cause:
   ChatGoogleGenerativeAI's max_retries wraps a SECOND, hidden retry layer
   inside the google-genai SDK itself (tenacity, backoff up to 60s, up to
   5 attempts by default) -- "4 retries" was compounding against that
   hidden layer, not adding to it linearly. Fixed by setting max_retries=0
   everywhere and relying on the fallback chain itself for redundancy,
   not retries within one tier.
3. Also hit a genuine per-model DAILY quota (not just transient): a live
   429 showed "limit: 20, model: gemini-3.8-flash" -- this is what
   motivated moving off a Gemini-only chain instead of just tuning retries
   further; a daily quota doesn't clear in seconds like a 503 does.
4. Replaced Gemini + Groq with OpenRouter (one OpenAI-compatible API,
   proxying many providers/models). Tested OpenRouter's own native
   request-level "models" fallback array first and found it behaved
   unpredictably (a confusing indirect failure through a specific
   provider, not a clean fall-through) -- not trusting an opaque
   server-side feature we can't fully verify, so this still uses our own
   invoke_with_fallback loop, just pointed at 3 different free OpenRouter
   models instead of 2 Gemini variants + Groq. Individual free-model
   failures here surface fast (well under a couple seconds, confirmed
   live), so a 3-model sequential loop stays fast even in the worst case.

Chain (deliberately 3 different underlying providers/architectures behind
OpenRouter, to reduce correlated-failure risk): qwen/qwen3.8-27b:free ->
liquid/lfm-2.5-2.6b:free -> nvidia/nemotron-3-super-120b-a12b:free.
"""

import logging
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config import get_settings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Confirmed live via a real models.list() call against OpenRouter plus real
# completions against each -- OpenRouter's free-model lineup has moved past
# the llama-3.x / gpt-3.5 names common in older docs/tutorials, same pattern
# as every other provider touched in this project.
GENERATION_MODEL = "qwen/qwen3.8-27b:free"
GENERATION_FALLBACK_MODEL = "liquid/lfm-2.5-2.6b:free"
GENERATION_SECOND_FALLBACK_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
ROUTING_MODEL = "qwen/qwen3.8-27b:free"  # cheap classification task, doesn't need the larger model

# max_retries=0: each tier gets exactly one fast attempt; the 3-model chain
# is the redundancy, not retrying within a single tier (see history above).
_TIMEOUT_SECONDS = 20
_MAX_RETRIES = 0

logger = logging.getLogger(__name__)


@lru_cache
def _build_llm(model: str) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=model,
        api_key=settings.openrouter_api_key,
        base_url=OPENROUTER_BASE_URL,
        timeout=_TIMEOUT_SECONDS,
        max_retries=_MAX_RETRIES,
    )


def get_generation_llm() -> ChatOpenAI:
    return _build_llm(GENERATION_MODEL)


def get_generation_fallback_llm() -> ChatOpenAI:
    return _build_llm(GENERATION_FALLBACK_MODEL)


def get_generation_second_fallback_llm() -> ChatOpenAI:
    return _build_llm(GENERATION_SECOND_FALLBACK_MODEL)


def get_routing_llm() -> ChatOpenAI:
    return _build_llm(ROUTING_MODEL)


def _model_label(model: BaseChatModel) -> str:
    return getattr(model, "model_name", None) or getattr(model, "model", None) or type(model).__name__


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
    """Normalize a chat model's .content. Plain string for every model
    seen through OpenRouter so far, but kept defensive -- Gemini's content
    came back as a list of content-part dicts in earlier testing, so this
    guards against any provider doing the same."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content)
