"""State schema for the RAG graph.

Node functions take a RAGState and return a partial dict of the fields they
update -- LangGraph merges that into the running state (plain overwrite per
field, no custom reducers needed here since nothing needs list-appending
semantics: each retrieval attempt replaces retrieved_docs outright rather
than accumulating across retries).
"""

from typing import Literal, TypedDict

from langchain_core.documents import Document

DomainFilter = Literal["agile-coaching", "claude-certification", "both"]


class Citation(TypedDict):
    index: int
    domain: str
    source: str
    heading_path: str


class RAGState(TypedDict, total=False):
    question: str
    domain_filter: DomainFilter  # what the user picked in the UI

    domains_to_search: list[str]  # decided by the routing node
    routing_reasoning: str

    retrieved_docs: list[Document]
    retrieval_attempts: int

    answer: str
    citations: list[Citation]
