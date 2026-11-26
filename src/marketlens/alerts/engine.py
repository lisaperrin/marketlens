"""Evaluate alert rules against a provider."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from marketlens.alerts.rules import AlertRules
from marketlens.analysis.indicators import bollinger, rsi
from marketlens.data.models import Period
from marketlens.data.provider import MarketDataProvider


@dataclass(frozen=True, slots=True)
class Alert:
    """One threshold that was crossed."""

    symbol: str
    kind: str
    """One of rsi_above, rsi_below, day_change_abs, price_above, price_below,
    bollinger_upper, bollinger_lower."""
    message: str
    value: float
    threshold: float

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable mapping."""
        return dataclasses.asdict(self)


def evaluate(
    symbols: Iterable[str],
    rules: AlertRules,
    provider: MarketDataProvider,
    period: Period = "6mo",
) -> list[Alert]:
    """Check every symbol (watchlist plus rule symbols) and return what crossed, by symbol.

    ``period`` is the history window used for RSI and the Bollinger Bands.
    """
    universe = sorted({s.upper() for s in symbols} | set(rules.symbols))
    alerts: list[Alert] = []
    for symbol in universe:
        alerts.extend(_check(symbol, rules.for_symbol(symbol), provider, period))
    return alerts


def _check(symbol: str, t: Any, provider: MarketDataProvider, period: Period) -> list[Alert]:
    found: list[Alert] = []
    quote = provider.get_quote(symbol)
    price, day = quote.price, quote.change_pct

    if t.price_above is not None and price >= t.price_above:
        found.append(
            Alert(
                symbol,
                "price_above",
                f"{symbol} at {price:,.2f}, above {t.price_above:,.2f}",
                price,
                t.price_above,
            )
        )
    if t.price_below is not None and price <= t.price_below:
        found.append(
            Alert(
                symbol,
                "price_below",
                f"{symbol} at {price:,.2f}, below {t.price_below:,.2f}",
                price,
                t.price_below,
            )
        )
    if abs(day) >= t.day_change_abs:
        found.append(
            Alert(
                symbol,
                "day_change_abs",
                f"{symbol} moved {day:+.2f}% today (limit {t.day_change_abs:.1f}%)",
                day,
                t.day_change_abs,
            )
        )

    close = provider.get_history(symbol, period=period)["Close"]
    rsi_series = rsi(close, 14).dropna()
    if not rsi_series.empty:
        rsi_now = float(rsi_series.iloc[-1])
        if rsi_now >= t.rsi_above:
            found.append(
                Alert(
                    symbol,
                    "rsi_above",
                    f"{symbol} RSI 14 at {rsi_now:.0f}, at or above {t.rsi_above:.0f}",
                    rsi_now,
                    t.rsi_above,
                )
            )
        elif rsi_now <= t.rsi_below:
            found.append(
                Alert(
                    symbol,
                    "rsi_below",
                    f"{symbol} RSI 14 at {rsi_now:.0f}, at or below {t.rsi_below:.0f}",
                    rsi_now,
                    t.rsi_below,
                )
            )

    if t.bollinger and not close.empty:
        bands = bollinger(close, 20).dropna()
        if not bands.empty:
            last = float(close.iloc[-1])
            upper, lower = float(bands["upper"].iloc[-1]), float(bands["lower"].iloc[-1])
            if last > upper:
                found.append(
                    Alert(
                        symbol,
                        "bollinger_upper",
                        f"{symbol} closed at {last:,.2f}, above the upper band {upper:,.2f}",
                        last,
                        upper,
                    )
                )
            elif last < lower:
                found.append(
                    Alert(
                        symbol,
                        "bollinger_lower",
                        f"{symbol} closed at {last:,.2f}, below the lower band {lower:,.2f}",
                        last,
                        lower,
                    )
                )
    return found
