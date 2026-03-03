import logging
from ..state import AnalysisState

logger = logging.getLogger(__name__)


def aggregate_results(state: AnalysisState) -> dict:
    """
    LangGraph node — Node 5 (final).
    Collects risk_assessment, alerts, and insights and builds the canonical
    response payload that FastAPI returns to the Laravel backend.
    """
    errors = state.get("fetch_errors") or []
    if errors:
        logger.warning(f"Pipeline completed with {len(errors)} error(s): {errors}")

    final_output = {
        "risk_assessment": state.get("risk_assessment"),
        "alerts":          state.get("alerts") or [],
        "insights":        state.get("insights"),
        "metadata": {
            "user_id":     state["user_id"],
            "asset_count": len(state["portfolio"]),
            "alert_count": len(state.get("alerts") or []),
            "errors":      errors,
            "partial":     len(errors) > 0,
        },
    }

    return {"final_output": final_output}
