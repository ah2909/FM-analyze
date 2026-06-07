import logging

from ..state import AnalysisState
from ..metrics import compute_concentration, compute_pnl, generate_alerts

logger = logging.getLogger(__name__)


def run_alert_generator(state: AnalysisState) -> dict:
    """LangGraph node — Node 3. Deterministic threshold alerts (no LLM)."""
    portfolio = state["portfolio"]
    market_data = state["market_data"]
    risk = state.get("risk_assessment") or {}

    allocations = risk.get("concentration_risk", {}).get("allocations") \
        or compute_concentration(portfolio, market_data)["allocations"]
    pnl_per_asset = risk.get("pnl_analysis", {}).get("per_asset") \
        or compute_pnl(portfolio, market_data)["per_asset"]

    alerts = generate_alerts(portfolio, market_data, allocations, pnl_per_asset)
    logger.info(f"alert_generator: {len(alerts)} alerts for user {state['user_id']}")
    return {"alerts": alerts}
