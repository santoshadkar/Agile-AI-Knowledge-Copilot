"""Load PDF/DOCX/Markdown source files into a single common representation:
markdown text with '#'/'##'/'###' headings. Downstream chunking (chunking.py)
only has to understand one format, and every source type gets to participate
in heading-aware splitting instead of blind fixed-size splitting.

DOCX heading detection is reliable (Word's paragraph styles say "Heading 1",
"Heading 2", ...). PDF has no such metadata, so heading detection there is a
heuristic over numbered sections and short Title-Case/ALL-CAPS lines -- good
enough for typically-structured reference docs, not guaranteed to be perfect
on every PDF layout.
"""

import re
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".md", ".pdf", ".docx"}

_NUMBERED_HEADING_RE = re.compile(r"^(\d+(\.\d+)*)\.?\s+\S")


def _pdf_heading_level(line: str) -> int | None:
    """Best-effort guess at whether a line of extracted PDF text is a heading,
    and if so, roughly what level. Returns None for ordinary body text."""
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return None

    match = _NUMBERED_HEADING_RE.match(stripped)
    if match:
        depth = match.group(1).count(".") + 1
        return min(depth, 3)

    word_count = len(stripped.split())
    if word_count == 0 or word_count > 8:
        return None
    # Trailing sentence punctuation strongly suggests body text, not a heading.
    if stripped.endswith((".", ",", ";")):
        return None
    if stripped.isupper():
        return 1
    if stripped.istitle():
        return 2
    return None


def load_pdf_as_markdown(path: Path) -> str:
    reader = PdfReader(str(path))
    lines: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            level = _pdf_heading_level(raw_line)
            lines.append(f"{'#' * level} {raw_line.strip()}" if level else raw_line)
    return "\n".join(lines)


def load_docx_as_markdown(path: Path) -> str:
    doc = DocxDocument(str(path))
    lines: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").lower() if para.style else ""
        if style == "title":
            lines.append(f"# {text}")
        elif style.startswith("heading"):
            level_str = style.replace("heading", "").strip()
            level = int(level_str) if level_str.isdigit() else 1
            lines.append(f"{'#' * min(level, 3)} {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def load_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_as_markdown(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return load_markdown(path)
    if suffix == ".pdf":
        return load_pdf_as_markdown(path)
    if suffix == ".docx":
        return load_docx_as_markdown(path)
    raise ValueError(
        f"Unsupported file type '{suffix}' for {path.name}. "
        f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )
