import asyncio
import logging

from ..state import OutlookState, AssetRef, AssetData, SourceResult
from .adapters import ADAPTERS
from ...config import RESEARCH

logger = logging.getLogger(__name__)


async def _bundle(asset: AssetRef, sem: asyncio.Semaphore) -> AssetData:
    async def _run(adapter) -> SourceResult:
        async with sem:
            return await adapter.fetch(asset)

    sources = await asyncio.gather(*[_run(a) for a in ADAPTERS])
    return AssetData(
        coingecko_id=asset["coingecko_id"],
        symbol=asset["symbol"],
        sources=list(sources),
        sources_available=[s["source_name"] for s in sources if s["available"]],
        sources_missing=[s["source_name"] for s in sources if not s["available"]],
    )


async def retrieve(state: OutlookState) -> dict:
    """Node 2 (deterministic): fan out adapters per asset under a concurrency cap."""
    sem = asyncio.Semaphore(RESEARCH.MAX_CONCURRENCY)
    bundles = await asyncio.gather(*[_bundle(a, sem) for a in state["assets"]])
    retrieved = {b["coingecko_id"]: b for b in bundles}
    logger.info(f"retrieve: fetched sources for {len(retrieved)} asset(s)")
    return {"retrieved": retrieved}
