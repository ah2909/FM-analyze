import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..graph.graph import analysis_graph

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Pydantic request/response models ─────────────────────────────────────────

class PortfolioAssetIn(BaseModel):
    symbol: str
    amount: float
    avg_price: float
    current_value: float = 0.0


class TransactionIn(BaseModel):
    symbol: str
    type: str       # "buy" | "sell"
    quantity: float
    price: float
    date: str


class AnalyzeRequest(BaseModel):
    user_id: str
    portfolio: list[PortfolioAssetIn]
    transactions: list[TransactionIn] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    success: bool
    data: dict | None = None
    error: str | None = None


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_portfolio(request: AnalyzeRequest):
    """
    Main analysis endpoint. Receives portfolio + transactions from the Laravel backend,
    runs the LangGraph pipeline (data_fetcher → risk → alerts → insights → aggregate),
    and returns structured results.
    """
    if not request.portfolio:
        raise HTTPException(status_code=400, detail="Portfolio cannot be empty")

    initial_state = {
        "user_id":         request.user_id,
        "portfolio":       [a.model_dump() for a in request.portfolio],
        "transactions":    [t.model_dump() for t in request.transactions],
        "market_data":     [],
        "fetch_errors":    [],
        "risk_assessment": None,
        "alerts":          [],
        "insights":        None,
        "final_output":    None,
    }

    try:
        result = await analysis_graph.ainvoke(initial_state)
        return AnalyzeResponse(success=True, data=result["final_output"])
    except Exception as exc:
        logger.error(f"Graph invocation failed for user {request.user_id}: {exc}")
        return AnalyzeResponse(success=False, error=str(exc))


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "portfolio-analyzer"}
