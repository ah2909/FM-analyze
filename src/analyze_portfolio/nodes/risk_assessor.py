import logging
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from ..state import AnalysisState, RiskAssessment
from ...config import LLM
from ...shared.utils import parse_json_response
from ..metrics import compute_concentration, compute_pnl, compute_volatility_assets

logger = logging.getLogger(__name__)


def _get_risk_schema() -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "risk_score": {
                "type": "NUMBER",
                "description": "Overall portfolio risk score from 1 (very low) to 10 (extreme risk)",
            },
            "overall_volatility": {
                "type": "STRING",
                "enum": ["low", "moderate", "high", "extreme"],
            },
            "summary": {
                "type": "STRING",
                "description": "2-3 sentence plain-English risk summary",
            },
        },
        "required": ["risk_score", "overall_volatility", "summary"],
    }


def _build_prompt(state: AnalysisState, concentration: dict, pnl: dict) -> str:
    market_data = state["market_data"]
    alloc_by_symbol = {a["symbol"]: a for a in concentration["allocations"]}
    pnl_by_symbol = {p["symbol"]: p for p in pnl["per_asset"]}

    lines = []
    for md in market_data:
        sym = md["symbol"].upper()
        alloc = alloc_by_symbol.get(sym, {})
        p = pnl_by_symbol.get(sym, {})
        lines.append(
            f"  {sym}: alloc={alloc.get('percentage', 0)}% ({alloc.get('flag', '')}), "
            f"PnL={p.get('pnl_pct', 0)}%, RSI={md['rsi']}, MACD={md['macd']}, "
            f"BB_upper={md['bb_upper']}, BB_lower={md['bb_lower']}"
        )

    return f"""You are an expert portfolio risk analyst specializing in cryptocurrency portfolios.

COMPUTED METRICS (authoritative — do not recompute):
Total invested: ${pnl['total_invested']:.2f}
Total current value: ${pnl['total_current_value']:.2f}
Unrealized PnL: ${pnl['unrealized_pnl']:.2f} ({pnl['unrealized_pnl_pct']:.2f}%)
Herfindahl index: {concentration['herfindahl_index']} (>0.25 = high concentration)

PER ASSET:
{chr(10).join(lines)}

Based on these figures and the RSI/MACD/Bollinger signals, judge:
- risk_score: overall risk from 1 (very low) to 10 (extreme)
- overall_volatility: one of low/moderate/high/extreme
- summary: 2-3 sentence plain-English risk summary
Return ONLY valid JSON matching the schema."""


def run_risk_assessor(state: AnalysisState) -> dict:
    """LangGraph node — Node 2. Deterministic metrics in Python; Gemini judges score/volatility/summary."""
    portfolio = state["portfolio"]
    market_data = state["market_data"]

    concentration = compute_concentration(portfolio, market_data)
    pnl = compute_pnl(portfolio, market_data)
    overbought, oversold = compute_volatility_assets(market_data)

    risk_score: float | None = None
    overall_volatility = "moderate"
    summary = ""
    errors: list[str] = []

    genai.configure(api_key=LLM.GEMINI_API_KEY)
    system_instruction = (
        "You are an expert crypto risk analyst. You must return ONLY valid, "
        "minified JSON that strictly follows the provided schema. No talk, no markdown fences."
    )
    model = genai.GenerativeModel(
        model_name=LLM.GEMINI_MODEL,
        system_instruction=system_instruction,
        generation_config=GenerationConfig(
            temperature=0.1,
            max_output_tokens=LLM.MAX_TOKENS,
            response_mime_type="application/json",
            response_schema=_get_risk_schema(),
        ),
    )

    try:
        prompt = _build_prompt(state, concentration, pnl)
        logger.debug(f"risk_assessor: Prompt: {prompt}")
        response = model.generate_content(prompt)
        logger.debug(f"risk_assessor: Raw response: {response.text}")

        judgment = parse_json_response(response.text)
        raw_score = judgment.get("risk_score")
        if raw_score is not None:
            risk_score = max(1.0, min(10.0, float(raw_score)))
        overall_volatility = judgment.get("overall_volatility", overall_volatility)
        summary = judgment.get("summary", "")
        logger.info(f"risk_assessor: Risk score={risk_score} for user {state['user_id']}")
    except Exception as exc:
        logger.error(f"risk_assessor LLM judgment failed: {exc}")
        errors.append(f"risk_assessor: {str(exc)}")

    risk: RiskAssessment = {
        "risk_score": risk_score,
        "concentration_risk": concentration,
        "volatility_risk": {
            "assets_overbought": overbought,
            "assets_oversold": oversold,
            "overall_volatility": overall_volatility,
        },
        "pnl_analysis": pnl,
        "summary": summary,
    }
    return {"risk_assessment": risk, "fetch_errors": errors}
