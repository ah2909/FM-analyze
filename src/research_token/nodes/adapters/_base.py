from datetime import datetime, timezone

from ...state import SourceResult


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def source(name: str, url: str, payload: dict, available: bool = True) -> SourceResult:
    return SourceResult(
        source_name=name,
        url=url,
        fetched_at=now_iso(),
        available=available,
        payload=payload,
    )


def unavailable(name: str, reason: str, url: str = "") -> SourceResult:
    return source(name, url, {"reason": reason}, available=False)
