"""Assemble quotes, fundamentals and statistics into one summary object."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from marketlens.analysis.indicators import rsi, sma
from marketlens.analysis.stats import (
    annualized_volatility,
    correlation_matrix,
    max_drawdown,
    sharpe_ratio,
    total_return,
)
from marketlens.data.models import Fundamentals, Period, Quote
from marketlens.data.provider import MarketDataProvider


@dataclass(frozen=True, slots=True)
class TickerSummary:
    """Everything the CLI and MCP server report about one symbol."""

    quote: Quote
    fundamentals: Fundamentals
    period: str
    last_close: float
    total_return: float
    annualized_volatility: float
    max_drawdown: float
    sharpe_ratio: float | None
    sma_50: float | None
    sma_200: float | None
    rsi_14: float | None

    @property
    def symbol(self) -> str:
        """Ticker symbol, taken from the quote."""
        return self.quote.symbol

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable mapping (datetimes as ISO strings, NaN as ``None``)."""
        data = {"symbol": self.symbol, **_clean(dataclasses.asdict(self))}
        data["quote"]["as_of"] = self.quote.as_of.isoformat()
        return data


@dataclass(frozen=True, slots=True)
class Comparison:
    """Side-by-side summaries plus the return correlation between them."""

    summaries: list[TickerSummary]
    correlation: pd.DataFrame

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable mapping; the matrix becomes a nested dict."""
        matrix: dict[str, dict[str, float | None]] = {
            str(row): {str(col): _nan_to_none(value) for col, value in values.items()}
            for row, values in self.correlation.to_dict(orient="index").items()
        }
        return {"summaries": [s.to_dict() for s in self.summaries], "correlation": matrix}


def summarize(symbol: str, provider: MarketDataProvider, period: Period = "1y") -> TickerSummary:
    """Fetch quote, fundamentals and history for ``symbol`` and compute the summary."""
    summary, _ = _summarize_with_close(symbol, provider, period)
    return summary


def _summarize_with_close(
    symbol: str, provider: MarketDataProvider, period: Period
) -> tuple[TickerSummary, pd.Series]:
    symbol = symbol.upper()
    close = provider.get_history(symbol, period=period)["Close"]
    summary = TickerSummary(
        quote=provider.get_quote(symbol),
        fundamentals=provider.get_fundamentals(symbol),
        period=period,
        last_close=float(close.iloc[-1]),
        total_return=total_return(close),
        annualized_volatility=annualized_volatility(close),
        max_drawdown=max_drawdown(close),
        sharpe_ratio=_nan_to_none(sharpe_ratio(close)),
        sma_50=_last(sma(close, 50)),
        sma_200=_last(sma(close, 200)),
        rsi_14=_last(rsi(close, 14)),
    )
    return summary, close


def compare(symbols: list[str], provider: MarketDataProvider, period: Period = "1y") -> Comparison:
    """Summarise each symbol and correlate their daily returns."""
    results = [_summarize_with_close(symbol, provider, period) for symbol in symbols]
    summaries = [summary for summary, _ in results]
    closes = {summary.symbol: close for summary, close in results}
    return Comparison(summaries=summaries, correlation=correlation_matrix(closes))


def _last(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return _nan_to_none(float(series.iloc[-1]))


def _nan_to_none(value: float | None) -> float | None:
    if value is None or math.isnan(value):
        return None
    return float(value)


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, float) and math.isnan(value):
        return None
    return value
