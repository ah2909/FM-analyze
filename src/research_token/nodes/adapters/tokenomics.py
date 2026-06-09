import asyncio
import logging

from pycoingecko import CoinGeckoAPI

from ...state import AssetRef, SourceResult
from ....config import COINGECKO
from ._base import source, unavailable

logger = logging.getLogger(__name__)

_NAME = "tokenomics"


def _cg() -> CoinGeckoAPI:
    return (
        CoinGeckoAPI(api_key=COINGECKO.API_KEY)
        if COINGECKO.IS_PRO
        else CoinGeckoAPI(demo_api_key=COINGECKO.API_KEY)
    )


def _normalize(coin: dict) -> dict:
    md = coin.get("market_data") or {}

    def _usd(field: str) -> float | None:
        v = (md.get(field) or {})
        return v.get("usd") if isinstance(v, dict) else v

    circ = md.get("circulating_supply")
    total = md.get("total_supply") or md.get("max_supply")
    mc = _usd("market_cap")
    fdv = _usd("fully_diluted_valuation")

    circulating_pct = round(circ / total, 4) if circ and total else None
    fdv_to_mc = round(fdv / mc, 3) if fdv and mc else None

    return {
        "circulating_pct": circulating_pct,
        "circulating_supply": circ,
        "total_supply": total,
        "market_cap": mc,
        "fdv": fdv,
        "fdv_to_mc": fdv_to_mc,
        "current_price": _usd("current_price") or 0.0,
        "categories": [c for c in (coin.get("categories") or []) if c],
        "chain": coin.get("asset_platform_id"),
    }


async def fetch(asset: AssetRef) -> SourceResult:
    coin_id = asset["coingecko_id"]
    url = f"https://www.coingecko.com/en/coins/{coin_id}"
    try:
        coin = await asyncio.to_thread(
            _cg().get_coin_by_id,
            id=coin_id,
            localization=False,
            tickers=False,
            market_data=True,
            community_data=False,
            developer_data=False,
            sparkline=False,
        )
        return source(_NAME, url, _normalize(coin))
    except Exception as exc:
        logger.warning(f"tokenomics fetch failed for {coin_id}: {exc}")
        return unavailable(_NAME, str(exc), url)
