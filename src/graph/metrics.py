"""Deterministic portfolio math — kept out of the LLM for accuracy and reproducibility."""
from typing import Any

from .state import PortfolioAsset, AssetIndicators, Alert


def _asset_for(symbol: str, portfolio: list[PortfolioAsset]) -> PortfolioAsset | dict:
    return next((a for a in portfolio if a["symbol"].upper() == symbol.upper()), {})


def _concentration_flag(pct: float) -> str:
    if pct >= 60:
        return "extreme"
    if pct >= 40:
        return "high"
    if pct >= 20:
        return "moderate"
    return "safe"


def compute_concentration(
    portfolio: list[PortfolioAsset], market_data: list[AssetIndicators]
) -> dict[str, Any]:
    """Allocation % per asset + Herfindahl-Hirschman index (0-1)."""
    values = {
        md["symbol"].upper(): md["current_price"] * _asset_for(md["symbol"], portfolio).get("amount", 0.0)
        for md in market_data
    }
    total = sum(values.values())

    allocations = []
    hhi = 0.0
    for symbol, value in values.items():
        pct = (value / total * 100) if total else 0.0
        hhi += (pct / 100) ** 2
        allocations.append({"symbol": symbol, "percentage": round(pct, 2), "flag": _concentration_flag(pct)})

    return {"allocations": allocations, "herfindahl_index": round(hhi, 4)}


def compute_pnl(
    portfolio: list[PortfolioAsset], market_data: list[AssetIndicators]
) -> dict[str, Any]:
    """Unrealized PnL totals and per-asset breakdown."""
    per_asset = []
    total_invested = 0.0
    total_current = 0.0

    for md in market_data:
        asset = _asset_for(md["symbol"], portfolio)
        amount = asset.get("amount", 0.0)
        avg_price = asset.get("avg_price", 0.0)
        invested = avg_price * amount
        current = md["current_price"] * amount
        pnl = current - invested
        per_asset.append({
            "symbol":  md["symbol"].upper(),
            "invested": round(invested, 2),
            "current":  round(current, 2),
            "pnl":      round(pnl, 2),
            "pnl_pct":  round((pnl / invested * 100) if invested else 0.0, 2),
        })
        total_invested += invested
        total_current += current

    unrealized = total_current - total_invested
    return {
        "total_invested":      round(total_invested, 2),
        "total_current_value": round(total_current, 2),
        "unrealized_pnl":      round(unrealized, 2),
        "unrealized_pnl_pct":  round((unrealized / total_invested * 100) if total_invested else 0.0, 2),
        "per_asset":           per_asset,
    }


def compute_volatility_assets(market_data: list[AssetIndicators]) -> tuple[list[str], list[str]]:
    """RSI-based overbought (>70) / oversold (<30) classification."""
    overbought = [md["symbol"].upper() for md in market_data if md["rsi"] is not None and md["rsi"] > 70]
    oversold = [md["symbol"].upper() for md in market_data if md["rsi"] is not None and md["rsi"] < 30]
    return overbought, oversold


def generate_alerts(
    portfolio: list[PortfolioAsset],
    market_data: list[AssetIndicators],
    allocations: list[dict[str, Any]],
    pnl_per_asset: list[dict[str, Any]],
) -> list[Alert]:
    """Threshold-based alerts — deterministic rules, no LLM."""
    alerts: list[Alert] = []

    for md in market_data:
        symbol = md["symbol"].upper()
        rsi = md["rsi"]
        if rsi is None:
            continue
        if rsi >= 80:
            alerts.append(Alert(
                type="rsi_critical", severity="critical", asset=symbol,
                message=f"{symbol} RSI at {rsi:.0f} — strongly overbought.",
                action="Consider taking profit or reducing exposure.",
            ))
        elif rsi <= 20:
            alerts.append(Alert(
                type="rsi_oversold", severity="high", asset=symbol,
                message=f"{symbol} RSI at {rsi:.0f} — oversold.",
                action="Potential accumulation zone; watch for reversal.",
            ))

    for alloc in allocations:
        if alloc["percentage"] > 40:
            sev = "critical" if alloc["percentage"] >= 60 else "high"
            alerts.append(Alert(
                type="imbalance", severity=sev, asset=alloc["symbol"],
                message=f"{alloc['symbol']} is {alloc['percentage']:.0f}% of the portfolio.",
                action="Diversify to reduce concentration risk.",
            ))

    for p in pnl_per_asset:
        if p["pnl_pct"] <= -35:
            alerts.append(Alert(
                type="stop_loss", severity="critical", asset=p["symbol"],
                message=f"{p['symbol']} down {p['pnl_pct']:.0f}% from average buy.",
                action="Review stop-loss; position is in deep drawdown.",
            ))
        elif p["pnl_pct"] <= -20:
            alerts.append(Alert(
                type="drawdown", severity="high", asset=p["symbol"],
                message=f"{p['symbol']} down {p['pnl_pct']:.0f}% from average buy.",
                action="Monitor closely; consider risk management.",
            ))
        elif p["pnl_pct"] >= 50:
            alerts.append(Alert(
                type="take_profit", severity="medium", asset=p["symbol"],
                message=f"{p['symbol']} up {p['pnl_pct']:.0f}% from average buy.",
                action="Consider locking in some gains.",
            ))

    return alerts
