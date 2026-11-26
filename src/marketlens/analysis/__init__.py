"""Pure, provider-free analytics over closing-price series."""

from marketlens.analysis.indicators import rsi, sma
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
    TickerSummary,
    compare,
    summarize,
)

__all__ = [
    "BenchmarkComparison",
    "Comparison",
    "TickerSummary",
    "aligned_total_returns",
    "annualized_volatility",
    "beta",
    "compare",
    "correlation_matrix",
    "daily_returns",
    "max_drawdown",
    "rsi",
    "sharpe_ratio",
    "sma",
    "summarize",
    "total_return",
]
