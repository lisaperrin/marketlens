"""Pure, provider-free analytics over closing-price series."""

from marketlens.analysis.indicators import rsi, sma
from marketlens.analysis.stats import (
    annualized_volatility,
    correlation_matrix,
    daily_returns,
    max_drawdown,
    sharpe_ratio,
    total_return,
)
from marketlens.analysis.summary import Comparison, TickerSummary, compare, summarize

__all__ = [
    "Comparison",
    "TickerSummary",
    "annualized_volatility",
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
