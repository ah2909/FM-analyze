import json
import logging
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from ..state import AnalysisState, Alert
from ...config.config import LLM

logger = logging.getLogger(__name__)


def _get_alert_schema() -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "alerts": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "type": {
                            "type": "STRING",
                            "enum": ["rsi_critical", "rsi_oversold", "imbalance",
                                     "stop_loss", "take_profit", "drawdown"],
                        },
                        "severity": {
                            "type": "STRING",
                            "enum": ["critical", "high", "medium", "low"],
                        },
                        "asset":   {"type": "STRING"},
                        "message": {"type": "STRING"},
                        "action":  {"type": "STRING"},
                    },
                    "required": ["type", "severity", "asset", "message", "action"],
                },
            },
        },
        "required": ["alerts"],
    }


def _build_prompt(state: AnalysisState) -> str:
    risk = state.get("risk_assessment") or {}
    market_data = state["market_data"]

    indicator_lines = [
        f"  {md['symbol']}: RSI={md['rsi']}, MACD={md['macd']}, "
        f"MACD_hist={md['macd_hist']}, BB_upper={md['bb_upper']}, "
        f"BB_lower={md['bb_lower']}, price=${md['current_price']:.2f}"
        for md in market_data
    ]

    return f"""You are a cryptocurrency portfolio alert system.

RISK CONTEXT (from previous analysis):
Risk Score: {risk.get('risk_score', 'N/A')}/10
Overall Volatility: {risk.get('volatility_risk', {}).get('overall_volatility', 'unknown')}

TECHNICAL INDICATORS PER ASSET:
{chr(10).join(indicator_lines)}

Generate actionable alerts for this portfolio. Prioritize:
- RSI > 80 (overbought/critical) or RSI < 20 (oversold)
- Extreme MACD divergence
- Any single asset exceeding 40% portfolio allocation (imbalance)
- Stop-loss trigger suggestions for losing positions
- Take-profit opportunities for large unrealized gains

Return ONLY valid JSON matching the schema."""


def run_alert_generator(state: AnalysisState) -> dict:
    """LangGraph node — Node 3. Generates prioritized alerts via Gemini structured output."""
    genai.configure(api_key=LLM.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=LLM.GEMINI_MODEL,
        generation_config=GenerationConfig(
            temperature=LLM.TEMPERATURE,
            max_output_tokens=LLM.MAX_TOKENS,
            response_mime_type="application/json",
            response_schema=_get_alert_schema(),
        ),
    )

    try:
        response = model.generate_content(_build_prompt(state))
        data = json.loads(response.text)
        alerts: list[Alert] = data.get("alerts", [])
        logger.info(f"alert_generator: {len(alerts)} alerts for user {state['user_id']}")
        # Return as list so the operator.add reducer appends correctly
        return {"alerts": alerts}
    except Exception as exc:
        logger.error(f"alert_generator failed: {exc}")
        return {"alerts": [], "fetch_errors": [f"alert_generator: {str(exc)}"]}
