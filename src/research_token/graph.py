from langgraph.graph import StateGraph, START, END

from .state import OutlookState
from .nodes.resolve_asset import resolve_asset
from .nodes.retrieve import retrieve
from .nodes.synthesize_asset import synthesize
from .nodes.persist import persist


def build_research_graph() -> StateGraph:
    """
    Single-symbol research-synthesis DAG:

        START → resolve_asset → retrieve → synthesize → persist → END

    Validation (anti-hallucination, price-prediction, citation checks) runs inside
    `synthesize` via the `validate_asset` module, with one retry then fail-soft.
    Per-symbol caching is handled by the Laravel backend (token_research:{symbol}).
    """
    builder = StateGraph(OutlookState)

    builder.add_node("resolve_asset", resolve_asset)
    builder.add_node("retrieve",      retrieve)
    builder.add_node("synthesize",    synthesize)
    builder.add_node("persist",       persist)

    builder.add_edge(START,           "resolve_asset")
    builder.add_edge("resolve_asset", "retrieve")
    builder.add_edge("retrieve",      "synthesize")
    builder.add_edge("synthesize",    "persist")
    builder.add_edge("persist",       END)

    return builder.compile()


# Compiled once at import — reused across all requests
research_graph = build_research_graph()
