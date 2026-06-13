import logging
from datetime import datetime, timezone

from ..state import OutlookState

logger = logging.getLogger(__name__)


def persist(state: OutlookState) -> dict:
    """
    Node 4 (final): assemble the single-asset payload. The Laravel backend caches it
    under token_research:{symbol} and emits over WebSocket; here we attach generated_at
    + the source set for reproducibility/freshness. No user_id — the cache is cross-user.
    """
    outlook = state.get("outlook")
    errors = state.get("errors") or []
    sources_used = (outlook or {}).get("data_coverage", {}).get("sources_available", [])

    final_output = {
        "outlook": outlook,
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources_used": sources_used,
            "partial": len(errors) > 0 or outlook is None,
            "errors": errors,
        },
    }
    logger.info(f"persist: outlook={'ok' if outlook else 'none'}, {len(errors)} errors")
    return {"final_output": final_output}
