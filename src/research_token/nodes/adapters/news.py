from ...state import AssetRef, SourceResult
from ._base import unavailable

_NAME = "news"


async def fetch(asset: AssetRef) -> SourceResult:
    # Stub: no web-search provider wired. Reported as missing so synthesis lowers confidence.
    return unavailable(_NAME, "news provider not configured")
