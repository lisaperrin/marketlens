"""Assemble quotes, fundamentals and statistics into one summary object."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from marketlens.analysis.indicators import bollinger, ema, macd, rsi, sma
from marketlens.analysis.stats import (
    aligned_total_returns,
    annualized_volatility,
    beta,
    correlation_matrix,
    max_drawdown,
    sharpe_ratio,
    total_return,
)
from marketlens.data.models import Fundamentals, Period, Quote
from marketlens.data.provider import MarketDataProvider


@dataclass(frozen=True, slots=True)
class BenchmarkComparison:
    """How a ticker did against a benchmark over the same period and shared dates."""

    symbol: str
    period: str
    benchmark_return: float | None
    """Benchmark total return over the dates both series share; ``None`` without overlap."""
    excess_return: float | None
    """Ticker return minus benchmark return over those same dates."""
    beta: float | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable mapping."""
        data: dict[str, Any] = _clean(dataclasses.asdict(self))
        return data


@dataclass(frozen=True, slots=True)
class IndicatorSnapshot:
    """Latest values of the secondary indicators; ``None`` where history is too short."""

    ema_20: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    bb_upper: float | None
    bb_middle: float | None
    bb_lower: float | None


SIGNAL_LOOKBACK = 5
"""Sessions to look back for crossover signals."""


def signals(close: pd.Series) -> tuple[str, ...]:
    """Short sentences for conditions worth a look; empty when nothing stands out.

    Checked: close outside the Bollinger Bands, MACD crossing its signal line in the last
    :data:`SIGNAL_LOOKBACK` sessions, RSI above 70 or below 30, SMA 50 crossing SMA 200 in
    the last :data:`SIGNAL_LOOKBACK` sessions.
    """
    found: list[str] = []
    if close.empty:
        return ()
    last = float(close.iloc[-1])

    bands = bollinger(close, 20)
    upper, lower = _last(bands["upper"]), _last(bands["lower"])
    if upper is not None and last > upper:
        found.append("Price closed above the upper Bollinger Band (20, 2 std)")
    elif lower is not None and last < lower:
        found.append("Price closed below the lower Bollinger Band (20, 2 std)")

    cross = _recent_cross(macd(close)["histogram"], min_abs=last * 0.0005)
    if cross is not None:
        days, direction = cross
        found.append(f"MACD crossed {direction} its signal line {_sessions_ago(days)}")

    rsi_now = _last(rsi(close, 14))
    if rsi_now is not None and rsi_now >= 70:
        found.append(f"RSI 14 at {rsi_now:.0f}: overbought territory (≥ 70)")
    elif rsi_now is not None and rsi_now <= 30:
        found.append(f"RSI 14 at {rsi_now:.0f}: oversold territory (≤ 30)")

    cross = _recent_cross(sma(close, 50) - sma(close, 200), min_abs=0.0)
    if cross is not None:
        days, direction = cross
        name = "Golden cross" if direction == "above" else "Death cross"
        found.append(f"{name}: SMA 50 moved {direction} SMA 200 {_sessions_ago(days)}")
    return tuple(found)


CROSS_RUN = 3
"""Sessions the difference must have spent on the other side for a sign change to count."""


def _recent_cross(difference: pd.Series, min_abs: float) -> tuple[int, str] | None:
    """Return (sessions ago, 'above'|'below') if ``difference`` changed sign recently.

    A change counts only if the previous :data:`CROSS_RUN` sessions were all on the other
    side and the new value's magnitude is at least ``min_abs``. Values within ``min_abs`` of
    zero belong to either side, so a line flickering around zero is not a crossover every
    day, while one that eases through zero before moving decisively is still caught.
    """
    values = difference.dropna().to_numpy(dtype="float64")
    for ago in range(SIGNAL_LOOKBACK):
        index = len(values) - 1 - ago
        if index < CROSS_RUN:
            return None
        current = values[index]
        run = values[index - CROSS_RUN : index]
        if abs(current) < min_abs:
            continue
        if current > 0 and (run <= min_abs).all():
            return ago, "above"
        if current < 0 and (run >= -min_abs).all():
            return ago, "below"
    return None


def _sessions_ago(days: int) -> str:
    if days == 0:
        return "today"
    return "1 session ago" if days == 1 else f"{days} sessions ago"


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
    indicators: IndicatorSnapshot
    signals: tuple[str, ...]
    benchmark: BenchmarkComparison | None = None
    """Present only when a benchmark symbol was requested."""

    @property
    def symbol(self) -> str:
        """Ticker symbol, taken from the quote."""
        return self.quote.symbol

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable mapping (datetimes as ISO strings, NaN as ``None``)."""
        data = {"symbol": self.symbol, **_clean(dataclasses.asdict(self))}
        data["quote"]["as_of"] = self.quote.as_of.isoformat()
        data["signals"] = list(self.signals)
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


def summarize(
    symbol: str,
    provider: MarketDataProvider,
    period: Period = "1y",
    benchmark: str | None = None,
) -> TickerSummary:
    """Fetch quote, fundamentals and history for ``symbol`` and compute the summary.

    With ``benchmark``, the benchmark's history over the same period is fetched too and the
    summary carries a :class:`BenchmarkComparison`.
    """
    benchmark_close = _benchmark_close(benchmark, provider, period)
    summary, _ = _summarize_with_close(symbol, provider, period, benchmark_close)
    return summary


def _benchmark_close(
    benchmark: str | None, provider: MarketDataProvider, period: Period
) -> tuple[str, pd.Series] | None:
    if benchmark is None:
        return None
    symbol = benchmark.upper()
    return symbol, provider.get_history(symbol, period=period)["Close"]


def compare_to_benchmark(
    close: pd.Series, benchmark_symbol: str, benchmark_close: pd.Series, period: str
) -> BenchmarkComparison:
    """Build the benchmark comparison for one close series."""
    asset_return, benchmark_return = aligned_total_returns(close, benchmark_close)
    excess = None
    if asset_return is not None and benchmark_return is not None:
        excess = asset_return - benchmark_return
    return BenchmarkComparison(
        symbol=benchmark_symbol,
        period=period,
        benchmark_return=benchmark_return,
        excess_return=excess,
        beta=beta(close, benchmark_close),
    )


def _summarize_with_close(
    symbol: str,
    provider: MarketDataProvider,
    period: Period,
    benchmark_close: tuple[str, pd.Series] | None = None,
) -> tuple[TickerSummary, pd.Series]:
    symbol = symbol.upper()
    close = provider.get_history(symbol, period=period)["Close"]
    comparison = None
    if benchmark_close is not None:
        comparison = compare_to_benchmark(close, benchmark_close[0], benchmark_close[1], period)
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
        indicators=_snapshot(close),
        signals=signals(close),
        benchmark=comparison,
    )
    return summary, close


def _snapshot(close: pd.Series) -> IndicatorSnapshot:
    macd_frame = macd(close)
    bands = bollinger(close, 20)
    return IndicatorSnapshot(
        ema_20=_last(ema(close, 20)),
        macd=_last(macd_frame["macd"]),
        macd_signal=_last(macd_frame["signal"]),
        macd_histogram=_last(macd_frame["histogram"]),
        bb_upper=_last(bands["upper"]),
        bb_middle=_last(bands["middle"]),
        bb_lower=_last(bands["lower"]),
    )


def compare(
    symbols: list[str],
    provider: MarketDataProvider,
    period: Period = "1y",
    benchmark: str | None = None,
) -> Comparison:
    """Summarise each symbol and correlate their daily returns."""
    benchmark_close = _benchmark_close(benchmark, provider, period)
    results = [_summarize_with_close(s, provider, period, benchmark_close) for s in symbols]
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
