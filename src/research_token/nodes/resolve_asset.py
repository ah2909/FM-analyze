import asyncio
import logging

from pycoingecko import CoinGeckoAPI

from ..state import OutlookState, AssetRef
from ...shared.coingecko_ids import symbol_to_id
from ...config import COINGECKO

logger = logging.getLogger(__name__)


def _resolve_sync(symbol: str, name: str) -> AssetRef | None:
    cg = (
        CoinGeckoAPI(api_key=COINGECKO.API_KEY)
        if COINGECKO.IS_PRO
        else CoinGeckoAPI(demo_api_key=COINGECKO.API_KEY)
    )
    coin_id = symbol_to_id(symbol, cg)
    if not coin_id:
        return None
    return AssetRef(symbol=symbol, name=name or symbol, coingecko_id=coin_id)


async def resolve_asset(state: OutlookState) -> dict:
    """Node 1 (deterministic): map the symbol → coingecko_id."""
    symbol = str(state.get("symbol", "")).upper()
    name = str(state.get("name", ""))
    asset = await asyncio.to_thread(_resolve_sync, symbol, name)
    if asset is None:
        logger.warning(f"resolve_asset: could not map symbol {symbol}")
        return {"asset": None,
                "errors": [{"node": "resolve_asset", "asset": symbol, "error": "unmappable symbol"}]}
    logger.info(f"resolve_asset: {symbol} → {asset['coingecko_id']}")
    return {"asset": asset}
