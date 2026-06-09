import asyncio
import logging

from pycoingecko import CoinGeckoAPI

from ..state import OutlookState, AssetRef
from ...shared.coingecko_ids import symbol_to_id
from ...config import COINGECKO

logger = logging.getLogger(__name__)


def _resolve_sync(raw_assets: list[dict]) -> tuple[list[AssetRef], list[dict]]:
    cg = (
        CoinGeckoAPI(api_key=COINGECKO.API_KEY)
        if COINGECKO.IS_PRO
        else CoinGeckoAPI(demo_api_key=COINGECKO.API_KEY)
    )
    by_id: dict[str, AssetRef] = {}
    errors: list[dict] = []

    for raw in raw_assets:
        symbol = str(raw.get("symbol", "")).upper()
        if not symbol:
            continue
        coin_id = symbol_to_id(symbol, cg)
        if not coin_id:
            errors.append({"node": "resolve_assets", "asset": symbol, "error": "unmappable symbol"})
            logger.warning(f"resolve_assets: could not map symbol {symbol}")
            continue

        amount = float(raw.get("amount", 0) or 0)
        avg_price = float(raw.get("avg_price", 0) or 0)

        if coin_id in by_id:
            # Same token held in two rows — merge into one, amount-weighted avg price.
            prev = by_id[coin_id]
            total = prev["amount"] + amount
            if total > 0:
                prev["avg_price"] = (prev["avg_price"] * prev["amount"] + avg_price * amount) / total
            prev["amount"] = total
        else:
            by_id[coin_id] = AssetRef(
                symbol=symbol,
                name=str(raw.get("name", symbol)),
                coingecko_id=coin_id,
                amount=amount,
                avg_price=avg_price,
            )

    return list(by_id.values()), errors


async def resolve_assets(state: OutlookState) -> dict:
    """Node 1 (deterministic): map symbols → coingecko_id, dedupe, drop unmappable."""
    assets, errors = await asyncio.to_thread(_resolve_sync, state["assets"])
    logger.info(f"resolve_assets: {len(assets)} unique assets, {len(errors)} dropped")
    return {"assets": assets, "errors": errors}
