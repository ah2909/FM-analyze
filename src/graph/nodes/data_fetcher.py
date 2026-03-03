import logging
import pandas as pd
import ta
from pycoingecko import CoinGeckoAPI

from ..state import AnalysisState, AssetIndicators
from ...config.config import COINGECKO, INDICATORS

logger = logging.getLogger(__name__)

# Hardcoded overrides for common coins or ones where the symbol-to-id is tricky.
_SYMBOL_TO_ID_OVERRIDES: dict[str, str] = {
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
}

# Cache for the full mapping from CoinGecko
_SYMBOL_MAP_CACHE: dict[str, str] = {}


def _get_symbol_to_id_map(cg: CoinGeckoAPI) -> dict[str, str]:
    """
    Fetches the full list of coins from CoinGecko and builds a symbol -> id mapping.
    Caches the result globally to avoid redundant heavy API calls.
    """
    global _SYMBOL_MAP_CACHE
    if _SYMBOL_MAP_CACHE and len(_SYMBOL_MAP_CACHE) > len(_SYMBOL_TO_ID_OVERRIDES):
        return _SYMBOL_MAP_CACHE

    _SYMBOL_MAP_CACHE = _SYMBOL_TO_ID_OVERRIDES.copy()

    try:
        coins = cg.get_coins_list()
        for c in coins:
            sym = c["symbol"].upper()
            cid = c["id"]
            
            if sym not in _SYMBOL_TO_ID_OVERRIDES:
                if sym not in _SYMBOL_MAP_CACHE or cid == sym.lower():
                    _SYMBOL_MAP_CACHE[sym] = cid

    except Exception as e:
        logger.error(f"Failed to fetch coins list from CoinGecko: {e}")

    return _SYMBOL_MAP_CACHE


def _symbol_to_id(symbol: str, cg: CoinGeckoAPI) -> str:
    """Resolves a symbol to a CoinGecko ID using cache + overrides."""
    mapping = _get_symbol_to_id_map(cg)
    return mapping.get(symbol.upper(), symbol.lower())


def _calculate_indicators(prices: list[float]) -> dict:
    """Run RSI, MACD, and Bollinger Bands via the ta library on a closing price series."""
    min_needed = INDICATORS.MACD_SLOW + INDICATORS.MACD_SIGNAL
    if len(prices) < min_needed:
        return {
            "rsi": None, "macd": None, "macd_signal": None,
            "macd_hist": None, "bb_upper": None, "bb_middle": None, "bb_lower": None,
        }

    series = pd.Series(prices, dtype=float)

    rsi_ind = ta.momentum.RSIIndicator(close=series, window=INDICATORS.RSI_PERIOD)
    macd_ind = ta.trend.MACD(
        close=series,
        window_fast=INDICATORS.MACD_FAST,
        window_slow=INDICATORS.MACD_SLOW,
        window_sign=INDICATORS.MACD_SIGNAL,
    )
    bb_ind = ta.volatility.BollingerBands(
        close=series,
        window=INDICATORS.BB_PERIOD,
        window_dev=INDICATORS.BB_STD_DEV,
    )

    def _last(s: pd.Series) -> float | None:
        val = s.iloc[-1]
        return None if pd.isna(val) else float(val)

    return {
        "rsi":         _last(rsi_ind.rsi()),
        "macd":        _last(macd_ind.macd()),
        "macd_signal": _last(macd_ind.macd_signal()),
        "macd_hist":   _last(macd_ind.macd_diff()),
        "bb_upper":    _last(bb_ind.bollinger_hband()),
        "bb_middle":   _last(bb_ind.bollinger_mavg()),
        "bb_lower":    _last(bb_ind.bollinger_lband()),
    }


def fetch_market_data(state: AnalysisState) -> dict:
    """
    LangGraph node — Node 1.
    Fetches OHLC history from CoinGecko and calculates technical indicators for
    every asset in the portfolio. Always emits one AssetIndicators entry per asset
    (uses stubs on failure so downstream LLM nodes never crash on a missing index).
    """
    cg = CoinGeckoAPI(demo_api_key=COINGECKO.API_KEY)
    market_data: list[AssetIndicators] = []
    errors: list[str] = []

    for asset in state["portfolio"]:
        symbol = asset["symbol"].upper()
        coin_id = _symbol_to_id(symbol, cg)

        try:
            ohlc = cg.get_coin_ohlc_by_id(
                id=coin_id,
                vs_currency="usd",
                days=COINGECKO.HISTORY_DAYS,
            )
            closes = [candle[4] for candle in ohlc]
            current_price = closes[-1] if closes else 0.0
            indicators = _calculate_indicators(closes)

            market_data.append(AssetIndicators(
                symbol=symbol,
                current_price=current_price,
                price_history=closes,
                **indicators,
            ))

        except Exception as exc:
            logger.error(f"Failed to fetch market data for {symbol}: {exc}")
            errors.append(f"{symbol}: {str(exc)}")
            # Stub entry so downstream nodes always have a full market_data list
            amount = asset.get("amount", 0) or 1e-9
            market_data.append(AssetIndicators(
                symbol=symbol,
                current_price=asset.get("current_value", 0.0) / amount,
                price_history=[],
                rsi=None, macd=None, macd_signal=None,
                macd_hist=None, bb_upper=None, bb_middle=None, bb_lower=None,
            ))

    logger.info(f"data_fetcher: fetched {len(market_data)} assets, {len(errors)} errors")
    return {"market_data": market_data, "fetch_errors": errors}
