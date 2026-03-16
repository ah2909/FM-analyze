import json
import logging
import re
from json_repair import repair_json
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from ..state import AnalysisState, RiskAssessment
from ...config.config import LLM

logger = logging.getLogger(__name__)


def _get_risk_schema() -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "risk_score": {
                "type": "NUMBER",
                "description": "Overall portfolio risk score from 1 (very low) to 10 (extreme risk)",
            },
            "concentration_risk": {
                "type": "OBJECT",
                "properties": {
                    "allocations": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "symbol":     {"type": "STRING"},
                                "percentage": {"type": "NUMBER"},
                                "flag": {
                                    "type": "STRING",
                                    "enum": ["safe", "moderate", "high", "extreme"],
                                },
                            },
                        },
                    },
                    "herfindahl_index": {
                        "type": "NUMBER",
                        "description": "HHI concentration index 0-1; above 0.25 is high concentration",
                    },
                },
                "required": ["allocations", "herfindahl_index"],
            },
            "volatility_risk": {
                "type": "OBJECT",
                "properties": {
                    "assets_overbought":  {"type": "ARRAY", "items": {"type": "STRING"}},
                    "assets_oversold":    {"type": "ARRAY", "items": {"type": "STRING"}},
                    "overall_volatility": {
                        "type": "STRING",
                        "enum": ["low", "moderate", "high", "extreme"],
                    },
                },
                "required": ["assets_overbought", "assets_oversold", "overall_volatility"],
            },
            "pnl_analysis": {
                "type": "OBJECT",
                "properties": {
                    "total_invested":       {"type": "NUMBER"},
                    "total_current_value":  {"type": "NUMBER"},
                    "unrealized_pnl":       {"type": "NUMBER"},
                    "unrealized_pnl_pct":   {"type": "NUMBER"},
                    "per_asset": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "symbol":  {"type": "STRING"},
                                "invested":{"type": "NUMBER"},
                                "current": {"type": "NUMBER"},
                                "pnl":     {"type": "NUMBER"},
                                "pnl_pct": {"type": "NUMBER"},
                            },
                        },
                    },
                },
                "required": ["total_invested", "total_current_value",
                             "unrealized_pnl", "unrealized_pnl_pct", "per_asset"],
            },
            "summary": {
                "type": "STRING",
                "description": "2-3 sentence plain-English risk summary",
            },
        },
        "required": ["risk_score", "concentration_risk", "volatility_risk",
                     "pnl_analysis", "summary"],
    }


def _build_prompt(state: AnalysisState) -> str:
    portfolio = state["portfolio"]
    market_data = state["market_data"]
    transactions = state["transactions"]

    total_value = sum(
        md["current_price"] * next(
            (a["amount"] for a in portfolio if a["symbol"] == md["symbol"]), 0.0
        )
        for md in market_data
    )

    lines = []
    for md in market_data:
        asset = next((a for a in portfolio if a["symbol"] == md["symbol"]), {})
        amount = asset.get("amount", 0.0)
        avg_price = asset.get("avg_price", 0.0)
        cur_val = md["current_price"] * amount
        alloc = (cur_val / total_value * 100) if total_value else 0.0
        pnl = (md["current_price"] - avg_price) * amount
        lines.append(
            f"  {md['symbol']}: amount={amount}, avg_buy=${avg_price:.2f}, "
            f"current=${md['current_price']:.2f}, value=${cur_val:.2f} ({alloc:.1f}%), "
            f"PnL=${pnl:.2f} | RSI={md['rsi']}, MACD={md['macd']}, "
            f"BB_upper={md['bb_upper']}, BB_lower={md['bb_lower']}"
        )

    return f"""You are an expert portfolio risk analyst specializing in cryptocurrency portfolios.

PORTFOLIO SUMMARY
Total Value: ${total_value:.2f}
Assets ({len(portfolio)} holdings):
{chr(10).join(lines)}

Transaction count: {len(transactions)}

Analyze this portfolio across all risk dimensions and provide a structured risk assessment.
Consider concentration risk (HHI), volatility signals from RSI/MACD/Bollinger Bands,
unrealized PnL and drawdown. Return ONLY valid JSON matching the schema."""


def _parse_json_response(text: str) -> dict:
    """Parse JSON from Gemini response, handling markdown fences and stray characters."""
    # Direct parse (happy path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences: ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Last resort: use json_repair to fix malformed JSON (unescaped quotes, missing commas, etc.)
    repaired = repair_json(cleaned)
    result = json.loads(repaired)
    if not isinstance(result, dict):
        raise ValueError(f"Cannot parse JSON from Gemini response. First 300 chars: {text[:300]!r}")
    return result


def run_risk_assessor(state: AnalysisState) -> dict:
    """LangGraph node — Node 2. Calls Gemini with structured output for risk analysis."""
    genai.configure(api_key=LLM.GEMINI_API_KEY)
    
    system_instruction = (
        "You are an expert crypto risk analyst. You must return ONLY valid, "
        "minified JSON that strictly follows the provided schema. No talk, no markdown fences."
    )
    
    model = genai.GenerativeModel(
        model_name=LLM.GEMINI_MODEL,
        system_instruction=system_instruction,
        generation_config=GenerationConfig(
            temperature=0.1,  # Lower temperature for stricter adherence
            max_output_tokens=LLM.MAX_TOKENS,
            response_mime_type="application/json",
            response_schema=_get_risk_schema(),
        ),
    )

    try:
        prompt = _build_prompt(state)
        logger.info(f"risk_assessor: Prompt: {prompt}")
        response = model.generate_content(prompt)
        logger.info(f"risk_assessor: Raw response: {response.text}")

        risk: RiskAssessment = _parse_json_response(response.text)
        logger.info(f"risk_assessor: Risk score={risk.get('risk_score')} for user {state['user_id']}")
        return {"risk_assessment": risk}
        
    except Exception as exc:
        logger.error(f"risk_assessor failed: {exc}")
        return {"risk_assessment": None, "fetch_errors": [f"risk_assessor: {str(exc)}"]}