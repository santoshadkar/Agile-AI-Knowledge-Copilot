from pathlib import Path

import pytest

from app.ingestion.loaders import load_as_markdown

SAMPLE_DOCS = Path(__file__).resolve().parent.parent / "sample_docs"


def test_markdown_loads_as_is():
    path = SAMPLE_DOCS / "agile-coaching" / "agile-maturity-framework.md"
    text = load_as_markdown(path)
    assert text.startswith("# Agile Maturity Assessment Framework")
    assert "## Dimension: Flow Metrics" in text


def test_docx_headings_convert_to_markdown():
    path = SAMPLE_DOCS / "agile-coaching" / "big-room-planning-guide.docx"
    text = load_as_markdown(path)
    assert "# Big Room Planning Facilitation Guide" in text
    assert "# Purpose" in text
    assert "# Pre-Event Preparation" in text
    assert "## Room Layout" in text


def test_pdf_numbered_headings_are_detected():
    path = SAMPLE_DOCS / "claude-certification" / "prompt-engineering-best-practices.pdf"
    text = load_as_markdown(path)
    assert "# 1. Introduction" in text
    assert "# 2. Be Clear and Direct" in text
    assert "# 5. Common Pitfalls" in text


def test_unsupported_extension_raises():
    with pytest.raises(ValueError, match="Unsupported file type"):
        load_as_markdown(Path("notes.txt"))
