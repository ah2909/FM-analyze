from __future__ import annotations
import operator
from typing import TypedDict, Annotated, Any


class PortfolioAsset(TypedDict):
    symbol: str
    amount: float
    avg_price: float
    current_value: float


class Transaction(TypedDict):
    symbol: str
    type: str        # "buy" | "sell"
    quantity: float
    price: float
    date: str


class AssetIndicators(TypedDict):
    symbol: str
    current_price: float
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    macd_hist: float | None
    bb_upper: float | None
    bb_middle: float | None
    bb_lower: float | None
    price_history: list[float]


class RiskAssessment(TypedDict):
    risk_score: float
    concentration_risk: dict[str, Any]
    volatility_risk: dict[str, Any]
    pnl_analysis: dict[str, Any]
    summary: str


class Alert(TypedDict):
    type: str        # "rsi_critical" | "rsi_oversold" | "imbalance" | "stop_loss" | "take_profit" | "drawdown"
    severity: str    # "critical" | "high" | "medium" | "low"
    asset: str
    message: str
    action: str


class Insights(TypedDict):
    best_performers: list[dict[str, Any]]
    worst_performers: list[dict[str, Any]]
    diversification_score: float
    diversification_notes: str
    market_trend_alignment: str
    recommendations: list[str]


class AnalysisState(TypedDict):
    # Input — set before graph.invoke()
    user_id: str
    portfolio: list[PortfolioAsset]
    transactions: list[Transaction]

    # Set by data_fetcher node
    market_data: list[AssetIndicators]
    fetch_errors: Annotated[list[str], operator.add]

    # Set by LLM nodes
    risk_assessment: RiskAssessment | None
    alerts: Annotated[list[Alert], operator.add]
    insights: Insights | None

    # Set by aggregator node
    final_output: dict[str, Any] | None
