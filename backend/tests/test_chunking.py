from app.ingestion.chunking import chunk_markdown

SAMPLE = """# Agile Maturity Assessment

Intro paragraph about why maturity assessments matter for coaching engagements.

## Dimension: Team Autonomy

Teams are scored on their ability to make decisions without escalation. """ + (
    "Lorem ipsum sentence filler to pad this section past the chunk size threshold. " * 15
) + """

## Dimension: Flow Metrics

Cycle time, throughput, and WIP limits are the primary signals here.
"""


def test_chunks_are_tagged_with_domain_and_source():
    chunks = chunk_markdown(SAMPLE, source="test.md", domain="agile-coaching")
    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.metadata["domain"] == "agile-coaching"
        assert chunk.metadata["source"] == "test.md"


def test_no_orphan_header_only_chunks():
    """Regression test: a heading immediately followed by a long paragraph
    used to produce a standalone chunk containing only the heading text
    (e.g. 27 chars, just "## Dimension: Team Autonomy") -- fixed by
    stripping headers from split content and prepending a breadcrumb to
    every resulting chunk instead. Every chunk should carry real content
    beyond just its own heading path."""
    chunks = chunk_markdown(SAMPLE, source="test.md", domain="agile-coaching")
    for chunk in chunks:
        breadcrumb = chunk.metadata.get("heading_path", "")
        content_without_breadcrumb = chunk.page_content.removeprefix(breadcrumb).strip()
        assert len(content_without_breadcrumb) > 20, f"near-empty chunk: {chunk.page_content!r}"


def test_long_section_splits_into_multiple_chunks_with_breadcrumb():
    chunks = chunk_markdown(SAMPLE, source="test.md", domain="agile-coaching")
    team_autonomy_chunks = [c for c in chunks if "Team Autonomy" in c.metadata.get("heading_path", "")]
    assert len(team_autonomy_chunks) > 1, "long section should split into more than one chunk"
    for chunk in team_autonomy_chunks:
        assert chunk.page_content.startswith("Agile Maturity Assessment > Dimension: Team Autonomy")


def test_short_sections_stay_as_one_chunk_each():
    chunks = chunk_markdown(SAMPLE, source="test.md", domain="agile-coaching")
    flow_metrics_chunks = [c for c in chunks if "Flow Metrics" in c.metadata.get("heading_path", "")]
    assert len(flow_metrics_chunks) == 1


def test_headingless_text_still_chunks_via_fallback():
    plain_text = "Just a plain paragraph with no markdown headings at all, still worth chunking."
    chunks = chunk_markdown(plain_text, source="plain.md", domain="claude-certification")
    assert len(chunks) == 1
    assert "plain paragraph" in chunks[0].page_content
    assert chunks[0].metadata["domain"] == "claude-certification"
