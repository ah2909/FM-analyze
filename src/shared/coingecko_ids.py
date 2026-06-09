import logging
from pycoingecko import CoinGeckoAPI

logger = logging.getLogger(__name__)

# Hardcoded overrides for common coins or ones where the symbol-to-id is tricky.
SYMBOL_TO_ID_OVERRIDES: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "XRP": "ripple",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
    "LTC": "litecoin",
    "ATOM": "cosmos",
    "NEAR": "near",
    "TRX": "tron",
    "SHIB": "shiba-inu",
    "TON": "the-open-network",
    "SUI": "sui",
    "APT": "aptos",
    "TIA": "celestia",
}

# Resolved symbol -> id, cached so each ambiguous symbol is looked up at most once.
_RESOLVED_CACHE: dict[str, str] = {}


def symbols_to_ids(symbols: list[str], cg: CoinGeckoAPI) -> dict[str, str]:
    """Resolve many tickers in one market-cap-ordered /coins/markets call (overrides + cache first)."""
    result: dict[str, str] = {}
    unresolved: list[str] = []
    for s in symbols:
        key = s.upper()
        if key in SYMBOL_TO_ID_OVERRIDES:
            result[key] = SYMBOL_TO_ID_OVERRIDES[key]
        elif key in _RESOLVED_CACHE:
            result[key] = _RESOLVED_CACHE[key]
        elif key not in unresolved:
            unresolved.append(key)

    if unresolved:
        try:
            # /coins/markets is market-cap-ordered, so the first hit per symbol is the canonical
            # coin for a shared ticker (e.g. ARB -> arbitrum, not a low-cap namesake).
            markets = cg.get_coins_markets(vs_currency="usd", symbols=",".join(k.lower() for k in unresolved))
            for coin in markets or []:
                sym = str(coin.get("symbol", "")).upper()
                if sym in unresolved and sym not in result:
                    result[sym] = coin["id"]
                    _RESOLVED_CACHE[sym] = coin["id"]
        except Exception as e:
            logger.error(f"symbols_to_ids: market lookup failed for {unresolved}: {e}")

    # Unmatched/errored symbols fall back to the lowercased ticker.
    for key in unresolved:
        result.setdefault(key, key.lower())
    return result


def symbol_to_id(symbol: str, cg: CoinGeckoAPI) -> str:
    """Resolve a single ticker to a CoinGecko id, disambiguating shared symbols by market cap."""
    return symbols_to_ids([symbol], cg)[symbol.upper()]
