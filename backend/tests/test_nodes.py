from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from app.graph.nodes import (
    ALL_DOMAINS,
    MAX_RETRIEVAL_ATTEMPTS,
    SUFFICIENCY_SCORE_THRESHOLD,
    generate,
    retrieve,
    route_query,
    should_retry,
)


# --- route_query -----------------------------------------------------------


def test_explicit_domain_filter_skips_routing_llm():
    with patch("app.graph.nodes.get_routing_llm") as mock_get_llm:
        result = route_query({"question": "anything", "domain_filter": "agile-coaching"})

    mock_get_llm.assert_not_called()
    assert result["domains_to_search"] == ["agile-coaching"]
    assert result["routing_reasoning"] == "explicit domain filter from the UI"


@pytest.mark.parametrize(
    "llm_reply,expected_domains",
    [
        ("agile-coaching", ["agile-coaching"]),
        ("claude-certification", ["claude-certification"]),
        ("both", ALL_DOMAINS),
        ("not sure, could be either", ALL_DOMAINS),  # ambiguous text defaults to both
    ],
)
def test_both_filter_routes_via_llm_classification(llm_reply, expected_domains):
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = MagicMock(content=llm_reply)

    with patch("app.graph.nodes.get_routing_llm", return_value=fake_llm):
        result = route_query({"question": "anything", "domain_filter": "both"})

    assert result["domains_to_search"] == expected_domains
    fake_llm.invoke.assert_called_once()
    # Gemini requires at least one "user" turn -- regression coverage for a
    # bug where only a SystemMessage was sent and every routing call failed
    # with "contents are required." (caught live, see the step-5 commit).
    sent_messages = fake_llm.invoke.call_args[0][0]
    assert any(type(m).__name__ == "HumanMessage" for m in sent_messages)


def test_routing_llm_failure_defaults_to_both_domains():
    fake_llm = MagicMock()
    fake_llm.invoke.side_effect = RuntimeError("503 UNAVAILABLE")

    with patch("app.graph.nodes.get_routing_llm", return_value=fake_llm):
        result = route_query({"question": "anything", "domain_filter": "both"})

    assert result["domains_to_search"] == ALL_DOMAINS


# --- retrieve ----------------------------------------------------------------


def _doc(domain: str, source: str, heading: str) -> Document:
    return Document(page_content="content", metadata={"domain": domain, "source": source, "heading_path": heading})


def test_retrieve_uses_domains_to_search_on_first_attempt():
    fake_results = [(_doc("agile-coaching", "a.md", "Intro"), 0.5)]
    fake_store = MagicMock()
    fake_store.similarity_search_with_score.return_value = fake_results

    with patch("app.graph.nodes.get_vector_store", return_value=fake_store):
        result = retrieve({"question": "q", "domain_filter": "agile-coaching", "domains_to_search": ["agile-coaching"]})

    assert result["domains_to_search"] == ["agile-coaching"]
    assert result["retrieval_attempts"] == 1
    assert result["retrieved_docs"][0].metadata["_score"] == 0.5


def test_retrieve_widens_to_both_domains_on_retry():
    fake_store = MagicMock()
    fake_store.similarity_search_with_score.return_value = []

    with patch("app.graph.nodes.get_vector_store", return_value=fake_store):
        result = retrieve(
            {
                "question": "q",
                "domain_filter": "agile-coaching",
                "domains_to_search": ["agile-coaching"],
                "retrieval_attempts": 1,  # this is the retry pass
            }
        )

    assert set(result["domains_to_search"]) == set(ALL_DOMAINS)
    assert result["retrieval_attempts"] == 2


# --- should_retry --------------------------------------------------------------


def test_should_retry_on_no_docs():
    assert should_retry({"retrieval_attempts": 1, "retrieved_docs": []}) == "retrieve"


def test_should_retry_on_low_score():
    docs = [Document(page_content="x", metadata={"_score": SUFFICIENCY_SCORE_THRESHOLD - 0.01})]
    assert should_retry({"retrieval_attempts": 1, "retrieved_docs": docs}) == "retrieve"


def test_generate_on_sufficient_score():
    docs = [Document(page_content="x", metadata={"_score": SUFFICIENCY_SCORE_THRESHOLD + 0.1})]
    assert should_retry({"retrieval_attempts": 1, "retrieved_docs": docs}) == "generate"


def test_generate_once_max_attempts_reached_even_with_low_score():
    docs = [Document(page_content="x", metadata={"_score": 0.0})]
    assert should_retry({"retrieval_attempts": MAX_RETRIEVAL_ATTEMPTS, "retrieved_docs": docs}) == "generate"


# --- generate ------------------------------------------------------------------


def test_generate_builds_citations_from_retrieved_docs():
    docs = [
        _doc("agile-coaching", "a.md", "Agile Guide > Intro"),
        _doc("claude-certification", "b.pdf", "API Basics"),
    ]

    with patch("app.graph.nodes.invoke_with_fallback", return_value="Answer text [1][2]."):
        result = generate({"question": "q", "retrieved_docs": docs})

    assert result["answer"] == "Answer text [1][2]."
    assert len(result["citations"]) == 2
    assert result["citations"][0] == {
        "index": 1,
        "domain": "agile-coaching",
        "source": "a.md",
        "heading_path": "Agile Guide > Intro",
    }
    assert result["citations"][1]["index"] == 2
    assert result["citations"][1]["source"] == "b.pdf"


def test_generate_with_no_retrieved_docs_has_no_citations():
    with patch("app.graph.nodes.invoke_with_fallback", return_value="I don't have enough information."):
        result = generate({"question": "q", "retrieved_docs": []})

    assert result["citations"] == []


def test_generate_propagates_error_when_both_models_fail():
    with patch("app.graph.nodes.invoke_with_fallback", side_effect=RuntimeError("Both Gemini models failed.")):
        with pytest.raises(RuntimeError):
            generate({"question": "q", "retrieved_docs": []})
