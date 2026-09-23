from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from app.ingestion.pipeline import ConfidentialityFlagError, PreparedIngestion
from app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


# --- /chat -----------------------------------------------------------------


def test_chat_rejects_empty_message():
    assert client.post("/chat", json={"message": ""}).status_code == 422


def test_chat_rejects_missing_message():
    assert client.post("/chat", json={}).status_code == 422


def test_chat_rejects_invalid_domain_filter():
    res = client.post("/chat", json={"message": "hi", "domain_filter": "not-a-real-domain"})
    assert res.status_code == 422


def test_chat_happy_path():
    fake_graph = MagicMock()
    fake_graph.invoke.return_value = {
        "answer": "Flow metrics track cycle time and throughput [1].",
        "citations": [{"index": 1, "domain": "agile-coaching", "source": "a.md", "heading_path": "Flow Metrics"}],
        "domains_to_search": ["agile-coaching"],
    }

    with patch("app.api.chat.get_rag_graph", return_value=fake_graph):
        res = client.post("/chat", json={"message": "What does flow metrics measure?", "domain_filter": "agile-coaching"})

    assert res.status_code == 200
    body = res.json()
    assert body["answer"] == "Flow metrics track cycle time and throughput [1]."
    assert body["citations"][0]["source"] == "a.md"
    assert body["domains_searched"] == ["agile-coaching"]

    # confirms the request was actually passed through to the graph, not just
    # short-circuited
    fake_graph.invoke.assert_called_once_with(
        {"question": "What does flow metrics measure?", "domain_filter": "agile-coaching"}
    )


def test_chat_returns_503_when_both_models_fail():
    fake_graph = MagicMock()
    fake_graph.invoke.side_effect = RuntimeError("Both Gemini models failed.")

    with patch("app.api.chat.get_rag_graph", return_value=fake_graph):
        res = client.post("/chat", json={"message": "hi"})

    assert res.status_code == 503
    assert "temporarily unavailable" in res.json()["detail"]


# --- /ingest -----------------------------------------------------------------


def test_ingest_rejects_invalid_domain():
    res = client.post(
        "/ingest",
        files={"file": ("doc.md", b"# Title\n\nbody", "text/markdown")},
        data={"domain": "not-a-real-domain"},
    )
    assert res.status_code == 422


def test_ingest_rejects_unsupported_file_type():
    res = client.post(
        "/ingest",
        files={"file": ("notes.txt", b"hello", "text/plain")},
        data={"domain": "agile-coaching"},
    )
    assert res.status_code == 400


def test_ingest_rejects_oversized_file():
    from app.api.ingest import MAX_FILE_SIZE_BYTES

    oversized = b"x" * (MAX_FILE_SIZE_BYTES + 1)
    res = client.post(
        "/ingest",
        files={"file": ("big.md", oversized, "text/markdown")},
        data={"domain": "agile-coaching"},
    )
    assert res.status_code == 413


def test_ingest_confidentiality_flag_returns_422_with_reasons():
    with patch(
        "app.api.ingest.prepare_ingestion",
        side_effect=ConfidentialityFlagError("nda.md", ["filename contains 'nda'"]),
    ):
        res = client.post(
            "/ingest",
            files={"file": ("nda.md", b"# Title\n\nbody", "text/markdown")},
            data={"domain": "agile-coaching"},
        )

    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["reasons"] == ["filename contains 'nda'"]
    assert detail["source"] == "nda.md"


def test_ingest_happy_path_responds_fast_and_schedules_background_commit():
    """The slow part (embed + upsert) must NOT run before the response is
    sent -- that synchronous design is exactly what caused a real 502 from
    Render's proxy on a large document (see pipeline.py's docstring).
    TestClient runs BackgroundTasks before client.post() returns, so
    asserting commit_ingestion was called here still proves the wiring is
    correct without needing a real embedding call."""
    fake_prepared = PreparedIngestion(
        source="doc.md",
        domain="agile-coaching",
        chunks=[Document(page_content="chunk text", metadata={})],
        confidentiality_flags=[],
    )

    with (
        patch("app.api.ingest.prepare_ingestion", return_value=fake_prepared),
        patch("app.api.ingest.commit_ingestion") as mock_commit,
    ):
        res = client.post(
            "/ingest",
            files={"file": ("doc.md", b"# Title\n\nSome body text.", "text/markdown")},
            data={"domain": "agile-coaching"},
        )

    assert res.status_code == 200
    body = res.json()
    assert body == {
        "source": "doc.md",
        "domain": "agile-coaching",
        "chunk_count": 1,
        "confidentiality_flags": [],
        "status": "processing",
    }
    mock_commit.assert_called_once_with(fake_prepared)
