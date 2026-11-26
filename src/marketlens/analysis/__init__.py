"""Pure, provider-free analytics over closing-price series."""

from marketlens.analysis.indicators import bollinger, ema, macd, rsi, sma
from marketlens.analysis.stats import (
    aligned_total_returns,
    annualized_volatility,
    beta,
    correlation_matrix,
    daily_returns,
    max_drawdown,
    sharpe_ratio,
    total_return,
)
from marketlens.analysis.summary import (
    BenchmarkComparison,
    Comparison,
    IndicatorSnapshot,
    TickerSummary,
    compare,
    signals,
    summarize,
)

__all__ = [
    "BenchmarkComparison",
    "Comparison",
    "IndicatorSnapshot",
    "TickerSummary",
    "aligned_total_returns",
    "annualized_volatility",
    "beta",
    "bollinger",
    "compare",
    "correlation_matrix",
    "daily_returns",
    "ema",
    "macd",
    "max_drawdown",
    "rsi",
    "sharpe_ratio",
    "signals",
    "sma",
    "summarize",
    "total_return",
]
