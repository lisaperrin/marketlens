"""Return and risk statistics over closing-price series."""

from __future__ import annotations

import math

import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def daily_returns(close: pd.Series) -> pd.Series:
    """Simple period-over-period returns, first observation dropped."""
    return close.pct_change().dropna()


def total_return(close: pd.Series) -> float:
    """Fractional return from the first close to the last (``0.10`` means +10 %)."""
    if len(close) < 2:
        return 0.0
    return float(close.iloc[-1] / close.iloc[0] - 1.0)


def annualized_volatility(close: pd.Series, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> float:
    """Sample standard deviation of returns scaled by the square root of time."""
    returns = daily_returns(close)
    if len(returns) < 2:
        return 0.0
    return float(returns.std() * math.sqrt(periods_per_year))


def max_drawdown(close: pd.Series) -> float:
    """Largest peak-to-trough fall as a negative fraction (``-0.25`` means a 25 % fall)."""
    if close.empty:
        return 0.0
    drawdown = close / close.cummax() - 1.0
    return float(min(drawdown.min(), 0.0))


def sharpe_ratio(
    close: pd.Series,
    risk_free: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> float:
    """Annualised Sharpe ratio; ``NaN`` when returns have no variance.

    ``risk_free`` is an annual rate (``0.04`` for 4 %) and is spread evenly per period.
    """
    excess = daily_returns(close) - risk_free / periods_per_year
    if len(excess) < 2 or excess.std() == 0.0 or math.isnan(float(excess.std())):
        return math.nan
    return float(excess.mean() / excess.std() * math.sqrt(periods_per_year))


def correlation_matrix(closes: dict[str, pd.Series]) -> pd.DataFrame:
    """Pearson correlation of daily returns across symbols, aligned on shared dates."""
    frame = pd.DataFrame({symbol: daily_returns(series) for symbol, series in closes.items()})
    return frame.dropna(how="any").corr()


def _aligned_returns(close: pd.Series, benchmark_close: pd.Series) -> pd.DataFrame:
    """Daily returns of both series on the dates they share (inner join)."""
    frame = pd.concat(
        {"asset": daily_returns(close), "benchmark": daily_returns(benchmark_close)},
        axis=1,
        join="inner",
    )
    return frame.dropna(how="any")


def beta(close: pd.Series, benchmark_close: pd.Series) -> float | None:
    """Beta of ``close`` to ``benchmark_close``.

    Covariance of daily returns divided by the benchmark's return variance, on shared dates.

    Returns ``None`` with fewer than 3 shared return observations or a benchmark that never moves.
    """
    frame = _aligned_returns(close, benchmark_close)
    if len(frame) < 3:
        return None
    variance = float(frame["benchmark"].var())
    if variance == 0.0 or math.isnan(variance):
        return None
    covariance = float(frame["asset"].cov(frame["benchmark"]))
    return covariance / variance


def aligned_total_returns(
    close: pd.Series, benchmark_close: pd.Series
) -> tuple[float | None, float | None]:
    """Total return of each series over the dates both cover; ``None`` with fewer than 2."""
    shared = close.index.intersection(benchmark_close.index)
    if len(shared) < 2:
        return None, None
    return total_return(close.loc[shared]), total_return(benchmark_close.loc[shared])
