"""Heuristic guard against accidentally ingesting proprietary/confidential material.

This is a best-effort scan, not a compliance control: it looks for common
markers (filename hints, boilerplate confidentiality banners) so an accidental
drag-and-drop of a work file gets caught before it's embedded and stored,
not a guarantee that every sensitive document will be caught.
"""

import re
from pathlib import Path

_FILENAME_MARKERS = (
    "confidential",
    "internal",
    "proprietary",
    "restricted",
    "do-not-share",
    "nda",
)

_CONTENT_PATTERNS = [
    re.compile(r"\bcompany\s+confidential\b", re.IGNORECASE),
    re.compile(r"\binternal\s+use\s+only\b", re.IGNORECASE),
    re.compile(r"\bproprietary\s+and\s+confidential\b", re.IGNORECASE),
    re.compile(r"\bdo\s+not\s+(distribute|forward|share)\b", re.IGNORECASE),
    re.compile(r"\ball\s+rights\s+reserved\b.{0,80}\binternal\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bclassification\s*:\s*(confidential|restricted|internal)\b", re.IGNORECASE),
]


def scan_for_confidentiality_markers(text: str, filename: str) -> list[str]:
    """Return a list of human-readable reasons this document looks risky to ingest.

    An empty list means nothing suspicious was found (not a guarantee of safety).
    """
    reasons: list[str] = []

    # Split on non-alphanumeric separators so a marker like "nda" only matches
    # as a whole filename token (e.g. "signed-nda.md"), not a substring hit
    # inside an unrelated word like "fundamentals".
    # Normalize to underscore-joined tokens and pad with delimiters so a
    # marker only matches as a whole token (or run of tokens), never as a
    # substring inside an unrelated word like "fundamentals" containing "nda".
    normalized_stem = "_" + re.sub(r"[^a-z0-9]+", "_", Path(filename).stem.lower()) + "_"
    for marker in _FILENAME_MARKERS:
        normalized_marker = "_" + re.sub(r"[^a-z0-9]+", "_", marker) + "_"
        if normalized_marker in normalized_stem:
            reasons.append(f"filename contains '{marker}'")

    for pattern in _CONTENT_PATTERNS:
        if pattern.search(text):
            reasons.append(f"document text matches confidentiality marker: /{pattern.pattern}/")

    return reasons
