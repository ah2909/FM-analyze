from __future__ import annotations
import logging
from datetime import date, datetime

from ..state import AssetData
from ..schemas import contains_price_prediction, contains_advice

logger = logging.getLogger(__name__)

# A source_id is simply the source name (each asset has at most one of each source).
_CITED_LISTS = ["bull_case", "bear_case", "key_risks", "catalysts_to_watch"]
_ITEM_TEXT_KEY = {"bull_case": "point", "bear_case": "point",
                  "key_risks": "risk", "catalysts_to_watch": "event"}


def _valid_ids(bundle: AssetData) -> set[str]:
    return set(bundle["sources_available"])


def _future_date_ok(value: str, today: date) -> bool:
    try:
        return datetime.fromisoformat(str(value)).date() >= today
    except (ValueError, TypeError):
        return False


def _item_ok(list_key: str, item: dict, valid_ids: set[str], today: date) -> bool:
    sids = item.get("source_ids") or []
    if not sids or not set(sids).issubset(valid_ids):
        return False
    text = str(item.get(_ITEM_TEXT_KEY[list_key], ""))
    if contains_price_prediction(text) or contains_advice(text):
        return False
    if list_key == "catalysts_to_watch" and not _future_date_ok(item.get("date", ""), today):
        return False
    return True


def validate(outlook: dict, bundle: AssetData, today: date | None = None) -> tuple[bool, list[str]]:
    """Returns (ok, errors). ok=False means at least one item violates §6/§9 rules."""
    today = today or date.today()
    valid_ids = _valid_ids(bundle)
    errors: list[str] = []

    if contains_price_prediction(str(outlook.get("summary", ""))):
        errors.append("summary contains a price prediction")

    for key in _CITED_LISTS:
        for i, item in enumerate(outlook.get(key) or []):
            if not _item_ok(key, item, valid_ids, today):
                errors.append(f"{key}[{i}] failed citation/date/guardrail check")

    return (not errors, errors)


def sanitize(outlook: dict, bundle: AssetData, today: date | None = None) -> dict:
    """Drop any item that violates the rules — guarantees a guardrail-safe outlook."""
    today = today or date.today()
    valid_ids = _valid_ids(bundle)
    cleaned = dict(outlook)

    if contains_price_prediction(str(cleaned.get("summary", ""))):
        cleaned["summary"] = "Evidence insufficient for a neutral summary."

    for key in _CITED_LISTS:
        cleaned[key] = [it for it in (cleaned.get(key) or []) if _item_ok(key, it, valid_ids, today)]
    return cleaned


# Exact numbers come from the adapter payloads, not the LLM — no hallucination/drift.
_TOKENOMICS_FIELDS = ["circulating_pct", "fdv_to_mc", "circulating_supply",
                      "total_supply", "market_cap", "fdv", "current_price"]


def _payload(bundle: AssetData, name: str) -> dict:
    for s in bundle.get("sources") or []:
        if s.get("source_name") == name and s.get("available"):
            return s.get("payload") or {}
    return {}


def _inject_metrics(outlook: dict, bundle: AssetData) -> None:
    tok = _payload(bundle, "tokenomics")
    if tok:
        snap = dict(outlook.get("tokenomics_snapshot") or {})
        for f in _TOKENOMICS_FIELDS:
            if tok.get(f) is not None:
                snap[f] = tok[f]
        outlook["tokenomics_snapshot"] = snap
        outlook["categories"] = tok.get("categories") or []
        outlook["chain"] = tok.get("chain")


def finalize(outlook: dict, bundle: AssetData) -> dict:
    """Inject deterministic fields (§6 asset + data_coverage + exact metrics)."""
    outlook["asset"] = bundle["symbol"]
    outlook["data_coverage"] = {
        "sources_available": bundle["sources_available"],
        "sources_missing":   bundle["sources_missing"],
    }
    _inject_metrics(outlook, bundle)
    return outlook
