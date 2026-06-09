from __future__ import annotations
import operator
from typing import TypedDict, Annotated, Any


class AssetRef(TypedDict):
    symbol: str
    name: str
    coingecko_id: str
    amount: float
    avg_price: float


class SourceResult(TypedDict):
    source_name: str       # "tokenomics" | "news" | "dev"
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
    # Input — set before graph.ainvoke(); one asset per request
    user_id: str
    assets: list[AssetRef]

    # Set by retrieve node
    retrieved: dict[str, AssetData]            # keyed by coingecko_id

    # Set by synthesize/validate nodes
    per_asset_outlook: list[dict[str, Any]]    # AssetOutlook objects (§6)

    # Set by persist node
    final_output: dict[str, Any] | None

    errors: Annotated[list[NodeError], operator.add]
