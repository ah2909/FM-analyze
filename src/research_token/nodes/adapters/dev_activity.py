from ...state import AssetRef, SourceResult
from ._base import unavailable

_NAME = "dev"


async def fetch(asset: AssetRef) -> SourceResult:
    # Stub: GitHub dev-activity adapter not wired. Reported as missing.
    return unavailable(_NAME, "dev-activity provider not configured")
