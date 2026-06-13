import asyncio
import logging

from ..state import OutlookState, AssetData, SourceResult
from .adapters import ADAPTERS
from ...config import RESEARCH

logger = logging.getLogger(__name__)


async def retrieve(state: OutlookState) -> dict:
    """Node 2 (deterministic): fan out adapters under a concurrency cap."""
    asset = state.get("asset")
    if not asset:
        return {"retrieved": None}

    sem = asyncio.Semaphore(RESEARCH.MAX_CONCURRENCY)

    async def _run(adapter) -> SourceResult:
        async with sem:
            return await adapter.fetch(asset)

    sources = await asyncio.gather(*[_run(a) for a in ADAPTERS])
    retrieved = AssetData(
        coingecko_id=asset["coingecko_id"],
        symbol=asset["symbol"],
        sources=list(sources),
        sources_available=[s["source_name"] for s in sources if s["available"]],
        sources_missing=[s["source_name"] for s in sources if not s["available"]],
    )
    logger.info(f"retrieve: fetched sources for {asset['coingecko_id']}")
    return {"retrieved": retrieved}
