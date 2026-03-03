import json
import logging
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from ..state import AnalysisState, Insights
from ...config.config import LLM

logger = logging.getLogger(__name__)


def _get_insight_schema() -> dict:
    performer_item = {
        "type": "OBJECT",
        "properties": {
            "symbol":  {"type": "STRING"},
            "pnl_pct": {"type": "NUMBER"},
            "reason":  {"type": "STRING"},
        },
        "required": ["symbol", "pnl_pct", "reason"],
    }
    return {
        "type": "OBJECT",
        "properties": {
            "best_performers":  {"type": "ARRAY", "items": performer_item},
            "worst_performers": {"type": "ARRAY", "items": performer_item},
            "market_trend_alignment": {
                "type": "STRING",
                "enum": ["strongly_aligned", "aligned", "neutral",
                         "misaligned", "strongly_misaligned"],
            },
            "recommendations": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "3-5 concrete actionable recommendations",
            },
        },
        "required": ["best_performers", "worst_performers", "market_trend_alignment", "recommendations"],
    }


def _build_prompt(state: AnalysisState) -> str:
    portfolio = state["portfolio"]
    market_data = state["market_data"]
    alerts = state.get("alerts") or []
    risk = state.get("risk_assessment") or {}

    perf_lines = []
    for md in market_data:
        asset = next((a for a in portfolio if a["symbol"] == md["symbol"]), {})
        avg_buy = asset.get("avg_price", 0.0)
        cur_price = md["current_price"]
        pnl_pct = ((cur_price - avg_buy) / avg_buy * 100) if avg_buy else 0.0
        perf_lines.append(
            f"  {md['symbol']}: avg_buy=${avg_buy:.2f}, current=${cur_price:.2f}, "
            f"PnL%={pnl_pct:.2f}%, RSI={md['rsi']}, MACD_hist={md['macd_hist']}"
        )

    critical_alerts = [a for a in alerts if a.get("severity") in ("critical", "high")]

    return f"""You are a strategic cryptocurrency portfolio advisor.

PORTFOLIO PERFORMANCE:
{chr(10).join(perf_lines)}

RISK SUMMARY:
Risk Score: {risk.get('risk_score', 'N/A')}/10
HHI: {risk.get('concentration_risk', {}).get('herfindahl_index', 'N/A')}

HIGH PRIORITY ALERTS ({len(critical_alerts)} critical/high):
{chr(10).join(a['message'] for a in critical_alerts) or 'None'}

Identify best and worst performers versus average buy price, score portfolio diversification
(0-100), assess alignment with current market trends using MACD and RSI signals, and provide
3-5 concrete actionable recommendations. Return ONLY valid JSON matching the schema."""


def run_insight_engine(state: AnalysisState) -> dict:
    """LangGraph node — Node 4. Generates strategic portfolio insights via Gemini."""
    genai.configure(api_key=LLM.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=LLM.GEMINI_MODEL,
        generation_config=GenerationConfig(
            temperature=LLM.TEMPERATURE,
            max_output_tokens=LLM.MAX_TOKENS,
            response_mime_type="application/json",
            response_schema=_get_insight_schema(),
        ),
    )

    try:
        response = model.generate_content(_build_prompt(state))
        insights: Insights = json.loads(response.text)
        logger.info(f"insight_engine: Analyzed successfully for user {state['user_id']}")
        return {"insights": insights}
    except Exception as exc:
        logger.error(f"insight_engine failed: {exc}")
        return {"insights": None, "fetch_errors": [f"insight_engine: {str(exc)}"]}
