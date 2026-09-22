from app.ingestion.safety import scan_for_confidentiality_markers


def test_clean_filename_and_content_are_not_flagged():
    assert scan_for_confidentiality_markers("Just a normal document about Scrum.", "sprint-guide.md") == []


def test_fundamentals_is_not_a_false_positive_for_nda():
    """Regression test: naive substring matching flagged
    "claude-api-fundamentals.md" because "fundamentals" contains the
    substring "nda" ("fu-nda-mentals"). Filename markers must match whole
    tokens only, not arbitrary substrings."""
    assert scan_for_confidentiality_markers("normal content", "claude-api-fundamentals.md") == []


def test_nda_filename_is_flagged():
    reasons = scan_for_confidentiality_markers("normal content", "signed-nda.md")
    assert any("nda" in reason for reason in reasons)


def test_confidential_filename_is_flagged():
    reasons = scan_for_confidentiality_markers("normal content", "q3-confidential-roadmap.pdf")
    assert any("confidential" in reason for reason in reasons)


def test_confidentiality_banner_in_content_is_flagged():
    reasons = scan_for_confidentiality_markers(
        "This document is Company Confidential and must not leave the org.", "notes.md"
    )
    assert len(reasons) > 0


def test_internal_use_only_banner_is_flagged():
    reasons = scan_for_confidentiality_markers("For Internal Use Only.", "notes.md")
    assert len(reasons) > 0
