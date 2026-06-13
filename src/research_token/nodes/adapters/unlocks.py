import logging
from collections import defaultdict
from datetime import datetime, timezone

import httpx

from ...state import AssetRef, SourceResult
from ....config import RESEARCH
from ._base import source, unavailable

logger = logging.getLogger(__name__)

_NAME = "unlocks"
_CDN = "https://defillama-datasets.llama.fi/emissions"
_PAGE = "https://defillama.com/unlocks"
_MAX_EVENTS = 6
_DAY = 86400
_HEADERS = {"User-Agent": "Mozilla/5.0 (portfolio-analyzer research bot)"}


def _future_daily(events: list[dict], now_ts: float) -> tuple[dict, dict]:
    # DefiLlama models linear vesting as per-day cliffs, so sum tokens per calendar day.
    daily: dict[str, float] = defaultdict(float)
    category: dict[str, tuple[float, str]] = {}
    for e in events:
        ts = e.get("timestamp", 0) or 0
        if ts < now_ts:
            continue
        toks_list = e.get("noOfTokens") or [0]
        toks = (toks_list[0] if toks_list else 0) or 0
        if toks <= 0:
            continue
        day = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
        daily[day] += toks
        if toks >= category.get(day, (0, ""))[0]:
            category[day] = (toks, e.get("category") or "")
    return daily, category


def _notable(daily: dict, category: dict, max_supply: float, cutoff_day: str) -> list[dict]:
    # A single-day spike above the supply-% floor is a cliff; the steady drip is not.
    if not max_supply:
        return []
    floor = max_supply * RESEARCH.UNLOCK_NOTABLE_PCT / 100
    items = [
        {
            "date": day,
            "tokens": round(toks),
            "pct_of_supply": round(toks / max_supply * 100, 2),
            "category": category[day][1],
            "type": "cliff",
        }
        for day, toks in daily.items()
        if toks >= floor and day <= cutoff_day
    ]
    # All items already clear the materiality floor, so prefer the soonest — never hide
    # next month's unlock behind a larger one further out.
    items.sort(key=lambda x: x["date"])
    return items[:_MAX_EVENTS]


def _window_pcts(events: list[dict], now_ts: float, max_supply: float) -> dict:
    if not max_supply:
        return {"pct_next_30d": None, "pct_next_90d": None, "pct_next_365d": None}
    win = {30: 0.0, 90: 0.0, 365: 0.0}
    for e in events:
        ts = e.get("timestamp", 0) or 0
        if ts < now_ts:
            continue
        toks_list = e.get("noOfTokens") or [0]
        toks = (toks_list[0] if toks_list else 0) or 0
        if toks <= 0:
            continue
        days_out = (ts - now_ts) / _DAY
        for w in win:
            if days_out <= w:
                win[w] += toks
    return {f"pct_next_{w}d": round(win[w] / max_supply * 100, 2) for w in win}


async def fetch(asset: AssetRef) -> SourceResult:
    coin_id = asset["coingecko_id"]
    page_url = f"{_PAGE}/{coin_id}"
    try:
        async with httpx.AsyncClient(timeout=RESEARCH.HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(f"{_CDN}/{coin_id}", headers=_HEADERS)
            if resp.status_code == 404:
                return unavailable(_NAME, "not tracked by DefiLlama unlocks", page_url)
            resp.raise_for_status()
            blob = resp.json()
    except Exception as exc:
        logger.warning(f"unlocks fetch failed for {coin_id}: {exc}")
        return unavailable(_NAME, str(exc), page_url)

    if blob.get("gecko_id") != coin_id:
        return unavailable(_NAME, "no gecko_id match in DefiLlama unlocks", page_url)

    events = (blob.get("metadata") or {}).get("events") or []
    max_supply = (blob.get("supplyMetrics") or {}).get("maxSupply") or 0
    now_ts = datetime.now(timezone.utc).timestamp()
    cutoff_day = datetime.fromtimestamp(
        now_ts + RESEARCH.UNLOCK_HORIZON_DAYS * _DAY, timezone.utc).strftime("%Y-%m-%d")

    daily, category = _future_daily(events, now_ts)
    notable = _notable(daily, category, max_supply, cutoff_day)
    windows = _window_pcts(events, now_ts, max_supply)

    if not notable and not any(windows.values()):
        return unavailable(_NAME, "no upcoming unlocks", page_url)

    payload = {
        "notable_unlocks": notable,
        "continuous_emission": windows,
        "max_supply": round(max_supply) if max_supply else None,
    }
    return source(_NAME, page_url, payload)
