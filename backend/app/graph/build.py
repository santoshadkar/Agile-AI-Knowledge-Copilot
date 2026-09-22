"""Wires the nodes into the actual graph:

    START -> route_query -> retrieve --(should_retry)--> retrieve  (loop, capped)
                                       \\-(should_retry)--> generate -> END
"""

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import generate, retrieve, route_query, should_retry
from app.graph.state import RAGState


def build_rag_graph() -> CompiledStateGraph:
    graph = StateGraph(RAGState)

    graph.add_node("route_query", route_query)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)

    graph.add_edge(START, "route_query")
    graph.add_edge("route_query", "retrieve")
    graph.add_conditional_edges("retrieve", should_retry, {"retrieve": "retrieve", "generate": "generate"})
    graph.add_edge("generate", END)

    return graph.compile()


@lru_cache
def get_rag_graph() -> CompiledStateGraph:
    return build_rag_graph()
