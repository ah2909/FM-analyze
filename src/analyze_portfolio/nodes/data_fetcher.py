import logging
import pandas as pd
import ta
from pycoingecko import CoinGeckoAPI

from ..state import AnalysisState, AssetIndicators
from ...shared.coingecko_ids import symbols_to_ids as _symbols_to_ids
from ...config import COINGECKO, INDICATORS

logger = logging.getLogger(__name__)


def _calculate_indicators(prices: list[float]) -> dict:
    """Run RSI, MACD, and Bollinger Bands; each indicator computed only if it has enough data."""
    result = {
        "rsi": None, "macd": None, "macd_signal": None,
        "macd_hist": None, "bb_upper": None, "bb_middle": None, "bb_lower": None,
    }
    n = len(prices)
    if n == 0:
        return result

    series = pd.Series(prices, dtype=float)

    def _last(s: pd.Series) -> float | None:
        val = s.iloc[-1]
        return None if pd.isna(val) else float(val)

    if n >= INDICATORS.RSI_PERIOD + 1:
        result["rsi"] = _last(
            ta.momentum.RSIIndicator(close=series, window=INDICATORS.RSI_PERIOD).rsi()
        )

    if n >= INDICATORS.MACD_SLOW + INDICATORS.MACD_SIGNAL:
        macd_ind = ta.trend.MACD(
            close=series,
            window_fast=INDICATORS.MACD_FAST,
            window_slow=INDICATORS.MACD_SLOW,
            window_sign=INDICATORS.MACD_SIGNAL,
        )
        result["macd"] = _last(macd_ind.macd())
        result["macd_signal"] = _last(macd_ind.macd_signal())
        result["macd_hist"] = _last(macd_ind.macd_diff())

    if n >= INDICATORS.BB_PERIOD:
        bb_ind = ta.volatility.BollingerBands(
            close=series,
            window=INDICATORS.BB_PERIOD,
            window_dev=INDICATORS.BB_STD_DEV,
        )
        result["bb_upper"] = _last(bb_ind.bollinger_hband())
        result["bb_middle"] = _last(bb_ind.bollinger_mavg())
        result["bb_lower"] = _last(bb_ind.bollinger_lband())

    if n < INDICATORS.MACD_SLOW + INDICATORS.MACD_SIGNAL:
        logger.warning(f"Only {n} candles — MACD/longer indicators may be unavailable")

    return result


def fetch_market_data(state: AnalysisState) -> dict:
    """
    LangGraph node — Node 1.
    Fetches OHLC history from CoinGecko and calculates technical indicators for
    every asset in the portfolio. Always emits one AssetIndicators entry per asset
    (uses stubs on failure so downstream LLM nodes never crash on a missing index).
    """
    cg = (
        CoinGeckoAPI(api_key=COINGECKO.API_KEY)
        if COINGECKO.IS_PRO
        else CoinGeckoAPI(demo_api_key=COINGECKO.API_KEY)
    )
    market_data: list[AssetIndicators] = []
    errors: list[str] = []

    # Resolve the whole portfolio in one market-cap-ordered call to stay within rate limits.
    coin_ids = _symbols_to_ids([a["symbol"] for a in state["portfolio"]], cg)

    for asset in state["portfolio"]:
        symbol = asset["symbol"].upper()
        coin_id = coin_ids[symbol]

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
