"""POST /chat -- runs the RAG graph (build step 3) and returns a cited answer.

Non-streaming, deliberately: the generation node's 3-model fallback chain
(see app/graph/llm.py) only works cleanly because nothing has been sent to
the client yet when a failure happens. Streaming tokens would mean a
mid-stream failure has no clean recovery -- restart the response, or show
the user a broken partial answer. Worth revisiting once the generation
chain's reliability is less of a live concern (see the step-3 and later
llm.py commits for what was observed testing this).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.graph.build import get_rag_graph
from app.graph.state import DomainFilter

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    domain_filter: DomainFilter = "both"


class CitationOut(BaseModel):
    index: int
    domain: str
    source: str
    heading_path: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    domains_searched: list[str]


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    graph = get_rag_graph()

    try:
        result = graph.invoke({"question": request.message, "domain_filter": request.domain_filter})
    except RuntimeError as exc:
        # Raised by invoke_with_fallback when every model in the chain
        # fails -- a real scenario, not hypothetical (see the step-3 and
        # later llm.py commits).
        raise HTTPException(
            status_code=503,
            detail="The generation model is temporarily unavailable. Please try again in a moment.",
        ) from exc

    return ChatResponse(
        answer=result["answer"],
        citations=[CitationOut(**c) for c in result["citations"]],
        domains_searched=result["domains_to_search"],
    )
