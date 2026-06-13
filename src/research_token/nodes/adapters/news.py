import logging
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx
from defusedxml.ElementTree import fromstring as xml_fromstring

from ...state import AssetRef, SourceResult
from ....config import RESEARCH
from ._base import source, unavailable

logger = logging.getLogger(__name__)

_NAME = "news"
_MAX_ARTICLES = 10
_BASE = "https://news.google.com/rss/search"
_HEADERS = {"User-Agent": "Mozilla/5.0 (portfolio-analyzer research bot)"}


def _query_url(asset: AssetRef) -> str:
    name = asset.get("name") or asset["symbol"]
    query = f'{name} {asset["symbol"]} crypto'
    return _BASE + "?" + urllib.parse.urlencode(
        {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})


def _parse(raw: bytes, cutoff: datetime) -> list[dict]:
    articles = []
    for it in xml_fromstring(raw).findall(".//item"):
        published = (it.findtext("pubDate") or "").strip()
        try:
            dt = parsedate_to_datetime(published)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            dt = None
        if dt is not None and dt < cutoff:
            continue
        src = it.find("{*}source")
        articles.append({
            "title":     (it.findtext("title") or "").strip(),
            "url":       (it.findtext("link") or "").strip(),
            "published": published,
            "source":    src.text.strip() if src is not None and src.text else "",
        })
        if len(articles) >= _MAX_ARTICLES:
            break
    return articles


async def fetch(asset: AssetRef) -> SourceResult:
    url = _query_url(asset)
    try:
        async with httpx.AsyncClient(timeout=RESEARCH.HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url, headers=_HEADERS)
            resp.raise_for_status()
        cutoff = datetime.now(timezone.utc) - timedelta(days=RESEARCH.NEWS_RECENCY_DAYS)
        articles = _parse(resp.content, cutoff)
    except Exception as exc:
        logger.warning(f"news fetch failed for {asset['symbol']}: {exc}")
        return unavailable(_NAME, str(exc), url)

    if not articles:
        return unavailable(_NAME, f"no news in last {RESEARCH.NEWS_RECENCY_DAYS}d", url)
    return source(_NAME, url, {"articles": articles})
