from __future__ import annotations
import operator
from typing import TypedDict, Annotated, Any


class AssetRef(TypedDict):
    symbol: str
    name: str
    coingecko_id: str


class SourceResult(TypedDict):
    source_name: str       # "tokenomics" | "news" | "dev" | "unlocks"
    url: str
    fetched_at: str        # ISO timestamp
    available: bool
    payload: dict[str, Any]


class AssetData(TypedDict):
    coingecko_id: str
    symbol: str
    sources: list[SourceResult]
    sources_available: list[str]
    sources_missing: list[str]


class NodeError(TypedDict):
    node: str
    asset: str | None
    error: str


class OutlookState(TypedDict):
    # Input — set before graph.ainvoke(); one token per request
    symbol: str
    name: str

    # Set by resolve_asset node
    asset: AssetRef | None

    # Set by retrieve node
    retrieved: AssetData | None

    # Set by synthesize/validate nodes
    outlook: dict[str, Any] | None        # AssetOutlook object (§6)

    # Set by persist node
    final_output: dict[str, Any] | None

    errors: Annotated[list[NodeError], operator.add]
