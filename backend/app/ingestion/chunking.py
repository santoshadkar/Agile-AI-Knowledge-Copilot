"""Heading-aware chunking, shared by every source format via loaders.py's
common markdown representation.

Two passes:
1. MarkdownHeaderTextSplitter groups text under its nearest # / ## / ### heading
   (headers stripped out of the body, kept as h1/h2/h3 metadata), so a chunk
   never straddles two unrelated sections.
2. RecursiveCharacterTextSplitter further splits any section still too long for
   one chunk, without crossing the section boundaries pass 1 found.

Every resulting chunk gets a "H1 > H2 > H3" breadcrumb prepended to its text
(not just left in metadata) -- it gives the embedding model heading context
on every chunk, including ones split out of the middle of a long section, and
it's what gets shown next to citations later.
"""

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

_HEADERS_TO_SPLIT_ON = [("#", "h1"), ("##", "h2"), ("###", "h3")]
_HEADER_KEYS = [key for _, key in _HEADERS_TO_SPLIT_ON]
_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 150

_header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=_HEADERS_TO_SPLIT_ON,
    strip_headers=True,
)
_char_splitter = RecursiveCharacterTextSplitter(
    chunk_size=_CHUNK_SIZE,
    chunk_overlap=_CHUNK_OVERLAP,
)


def _heading_breadcrumb(metadata: dict) -> str:
    return " > ".join(metadata[key] for key in _HEADER_KEYS if metadata.get(key))


def chunk_markdown(markdown_text: str, *, source: str, domain: str) -> list[Document]:
    """Split markdown text into Documents tagged with domain + source metadata,
    ready to embed and upsert."""
    sections = _header_splitter.split_text(markdown_text)
    if not sections:
        sections = [Document(page_content=markdown_text)]

    chunks = _char_splitter.split_documents(sections)

    result: list[Document] = []
    for chunk in chunks:
        if not chunk.page_content.strip():
            continue
        breadcrumb = _heading_breadcrumb(chunk.metadata)
        content = f"{breadcrumb}\n\n{chunk.page_content}" if breadcrumb else chunk.page_content
        chunk.metadata["source"] = source
        chunk.metadata["domain"] = domain
        chunk.metadata["heading_path"] = breadcrumb
        result.append(Document(page_content=content, metadata=chunk.metadata))

    return result
