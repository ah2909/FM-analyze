import asyncio
import logging

from pycoingecko import CoinGeckoAPI

from ...state import AssetRef, SourceResult
from ....config import COINGECKO
from ._base import source, unavailable

logger = logging.getLogger(__name__)

_NAME = "dev"


def _cg() -> CoinGeckoAPI:
    return (
        CoinGeckoAPI(api_key=COINGECKO.API_KEY)
        if COINGECKO.IS_PRO
        else CoinGeckoAPI(demo_api_key=COINGECKO.API_KEY)
    )


def _normalize(coin: dict) -> dict:
    dev = coin.get("developer_data") or {}
    cad = dev.get("code_additions_deletions_4_weeks") or {}
    repos = ((coin.get("links") or {}).get("repos_url") or {}).get("github") or []

    return {
        "stars": dev.get("stars"),
        "forks": dev.get("forks"),
        "subscribers": dev.get("subscribers"),
        "total_issues": dev.get("total_issues"),
        "closed_issues": dev.get("closed_issues"),
        "pull_requests_merged": dev.get("pull_requests_merged"),
        "pull_request_contributors": dev.get("pull_request_contributors"),
        "commit_count_4_weeks": dev.get("commit_count_4_weeks"),
        "code_additions_4_weeks": cad.get("additions"),
        "code_deletions_4_weeks": cad.get("deletions"),
        "repos": [r for r in repos if r][:5],
    }


def _has_signal(payload: dict) -> bool:
    return any(payload.get(f) for f in
              ("stars", "forks", "commit_count_4_weeks", "total_issues", "repos"))


async def fetch(asset: AssetRef) -> SourceResult:
    coin_id = asset["coingecko_id"]
    url = f"https://www.coingecko.com/en/coins/{coin_id}"
    try:
        coin = await asyncio.to_thread(
            _cg().get_coin_by_id,
            id=coin_id,
            localization=False,
            tickers=False,
            market_data=False,
            community_data=False,
            developer_data=True,
            sparkline=False,
        )
    except Exception as exc:
        logger.warning(f"dev fetch failed for {coin_id}: {exc}")
        return unavailable(_NAME, str(exc), url)

    payload = _normalize(coin)
    if not _has_signal(payload):
        return unavailable(_NAME, "no tracked repository / dev activity", url)
    return source(_NAME, url, payload)
