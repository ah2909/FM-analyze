import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..research_token.graph import research_graph

logger = logging.getLogger(__name__)
router = APIRouter()


class ResearchRequest(BaseModel):
    symbol: str
    name: str = ""
    user_id: str = ""


class ResearchResponse(BaseModel):
    success: bool
    data: dict | None = None
    error: str | None = None


@router.post("/api/research", response_model=ResearchResponse)
async def research_token(request: ResearchRequest):
    """
    Single-symbol research-synthesis outlook. Runs the LangGraph pipeline
    (resolve → retrieve → synthesize) and returns one §6 outlook with cited sources.
    No price prediction. Caching is handled by the Laravel backend.
    """
    if not request.symbol.strip():
        raise HTTPException(status_code=400, detail="symbol cannot be empty")

    initial_state = {
        "user_id":           request.user_id,
        "assets":            [{"symbol": request.symbol, "name": request.name or request.symbol,
                               "amount": 0.0, "avg_price": 0.0}],
        "retrieved":         {},
        "per_asset_outlook": [],
        "final_output":      None,
        "errors":            [],
    }

    try:
        result = await research_graph.ainvoke(initial_state)
        return ResearchResponse(success=True, data=result["final_output"])
    except Exception as exc:
        logger.error(f"Research graph failed for {request.symbol}: {exc}")
        return ResearchResponse(success=False, error=str(exc))
