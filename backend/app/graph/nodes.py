"""The four pieces of the RAG graph: route -> retrieve -> (retry?) -> generate.

Kept as plain functions taking/returning RAGState so they're easy to unit
test in isolation (build step 7) without spinning up the whole graph.
"""

import logging
from typing import Literal

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.graph.llm import (
    extract_text,
    get_generation_fallback_llm,
    get_generation_llm,
    get_routing_llm,
    invoke_with_fallback,
)
from app.graph.state import Citation, RAGState
from app.resilience import voyage_retry
from app.vectorstore.qdrant_client import get_vector_store

logger = logging.getLogger(__name__)

ALL_DOMAINS = ["agile-coaching", "claude-certification"]

RETRIEVAL_K = 5
MAX_RETRIEVAL_ATTEMPTS = 2
# Calibrated against this project's real corpus + voyage-4-lite: a genuinely
# relevant top match scored ~0.47, an unrelated query's top match scored
# ~0.13 (see the pipeline verification notes in the step-2 commits). 0.35
# sits well clear of the irrelevant-query noise floor.
SUFFICIENCY_SCORE_THRESHOLD = 0.35


def route_query(state: RAGState) -> dict:
    """Decide which domain(s) to search.

    An explicit single-domain filter from the UI is respected outright --
    no LLM call needed, and it's what the person asked for. "both" is where
    routing actually does something: a cheap classification call decides
    whether the query is really cross-domain or clearly belongs to one,
    so a question that's obviously agile-only doesn't pull in unrelated
    Claude-certification noise. Defaults to both domains on any failure or
    ambiguity -- under-covering silently would be worse than the query
    running a bit broader than strictly necessary.
    """
    domain_filter = state["domain_filter"]

    if domain_filter != "both":
        return {"domains_to_search": [domain_filter], "routing_reasoning": "explicit domain filter from the UI"}

    routing_system_prompt = (
        "You are routing a question to one or both knowledge domains of a retrieval system:\n"
        "- agile-coaching: agile maturity assessment, Scrum/SAFe, Big Room Planning, team facilitation\n"
        "- claude-certification: the Claude API, prompt engineering, building with Claude\n\n"
        "Reply with exactly one line, one of: agile-coaching / claude-certification / both. "
        "Use \"both\" if the question could plausibly draw on either domain or you're unsure."
    )

    try:
        # Routing already uses the lite model, so there's no cheaper fallback
        # to drop to -- just one call, relying on the client's own built-in
        # retries (see llm.py) rather than invoke_with_fallback's two-model
        # dance, which would only be calling the same model against itself.
        # Gemini requires at least one "user" turn -- a SystemMessage alone
        # fails with "contents are required." (caught live while building
        # this: it degraded to the safe "both" default rather than crashing,
        # but the routing feature itself was silently doing nothing).
        messages = [
            SystemMessage(content=routing_system_prompt),
            HumanMessage(content=f"Question: {state['question']}"),
        ]
        raw = extract_text(get_routing_llm().invoke(messages))
        decision = raw.strip().lower()
    except Exception as exc:
        logger.warning("Routing LLM call failed (%s); defaulting to both domains", exc)
        return {"domains_to_search": ALL_DOMAINS, "routing_reasoning": "routing call failed, defaulted to both"}

    if "agile-coaching" in decision and "claude-certification" not in decision:
        domains = ["agile-coaching"]
    elif "claude-certification" in decision and "agile-coaching" not in decision:
        domains = ["claude-certification"]
    else:
        domains = ALL_DOMAINS

    return {"domains_to_search": domains, "routing_reasoning": raw.strip()}


@voyage_retry
def _similarity_search_with_backoff(vector_store, question: str, domain_filter: Filter):
    return vector_store.similarity_search_with_score(question, k=RETRIEVAL_K, filter=domain_filter)


def retrieve(state: RAGState) -> dict:
    """Run similarity search filtered to domains_to_search.

    On a retry (attempts > 0), widens to both domains first if the previous
    attempt was scoped to just one -- the cheapest way to improve recall
    when the first pass came back weak.
    """
    attempts = state.get("retrieval_attempts", 0)
    domains = state["domains_to_search"]
    if attempts > 0 and len(domains) < len(ALL_DOMAINS):
        domains = ALL_DOMAINS

    domain_filter = Filter(
        should=[FieldCondition(key="metadata.domain", match=MatchValue(value=d)) for d in domains]
    )

    vector_store = get_vector_store()
    results = _similarity_search_with_backoff(vector_store, state["question"], domain_filter)

    docs: list[Document] = []
    for doc, score in results:
        doc.metadata["_score"] = score
        docs.append(doc)

    return {
        "retrieved_docs": docs,
        "domains_to_search": domains,
        "retrieval_attempts": attempts + 1,
    }


def should_retry(state: RAGState) -> Literal["retrieve", "generate"]:
    """Conditional edge: is the first retrieval pass good enough, or is
    another attempt (with widened domains) worth it?"""
    if state.get("retrieval_attempts", 0) >= MAX_RETRIEVAL_ATTEMPTS:
        return "generate"

    docs = state.get("retrieved_docs", [])
    best_score = max((doc.metadata.get("_score", 0.0) for doc in docs), default=0.0)

    if not docs or best_score < SUFFICIENCY_SCORE_THRESHOLD:
        return "retrieve"
    return "generate"


_SYSTEM_PROMPT = (
    "You are a knowledge assistant answering from a fixed set of source documents. "
    "Answer ONLY using the numbered context chunks below -- do not use outside knowledge. "
    "Cite every claim with the bracket number(s) of the chunk(s) it came from, like [1] or [2][3]. "
    "If the context doesn't contain enough information to answer, say so plainly rather than guessing."
)


def _format_context(docs: list[Document]) -> str:
    parts = []
    for i, doc in enumerate(docs, start=1):
        heading = doc.metadata.get("heading_path") or doc.metadata.get("source", "")
        parts.append(f"[{i}] ({doc.metadata.get('domain')} :: {heading})\n{doc.page_content}")
    return "\n\n".join(parts)


def generate(state: RAGState) -> dict:
    docs = state.get("retrieved_docs", [])
    context = _format_context(docs)

    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=f"Context:\n\n{context}\n\nQuestion: {state['question']}"),
    ]

    answer = invoke_with_fallback(messages, primary=get_generation_llm(), fallback=get_generation_fallback_llm())

    citations: list[Citation] = [
        Citation(
            index=i,
            domain=doc.metadata.get("domain", ""),
            source=doc.metadata.get("source", ""),
            heading_path=doc.metadata.get("heading_path", ""),
        )
        for i, doc in enumerate(docs, start=1)
    ]

    return {"answer": answer, "citations": citations}
