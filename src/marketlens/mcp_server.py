"""A Model Context Protocol server exposing MarketLens to Claude and other MCP clients.

Run it over stdio with ``marketlens-mcp`` (or ``uvx --from marketlens marketlens-mcp``).
Every tool returns plain JSON-compatible dicts; MarketLens errors surface as tool errors
with a readable message, never as opaque server failures.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from marketlens import __version__
from marketlens.analysis.summary import compare, summarize
from marketlens.data.cache import CachedProvider
from marketlens.data.models import PERIODS, Period
from marketlens.data.provider import MarketDataProvider
from marketlens.data.yfinance_provider import YFinanceProvider
from marketlens.errors import MarketLensError
from marketlens.portfolio.holdings import load_portfolio
from marketlens.portfolio.valuation import value_portfolio
from marketlens.report.brief import build_brief, quote_to_dict

server = MCPServer(
    name="marketlens",
    version=__version__,
    instructions=(
        "Market data from Yahoo Finance via yfinance. Prices are delayed; nothing here is "
        "investment advice. Use analyze_ticker for one symbol, compare_tickers for several, "
        "portfolio_summary for a holdings TOML file and market_brief for a quick overview."
    ),
)


def _default_provider() -> MarketDataProvider:
    return CachedProvider(YFinanceProvider())


provider_factory: Callable[[], MarketDataProvider] = _default_provider
"""Returns the provider tools use. Tests replace this with an in-memory provider."""


def _tool_errors[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Translate MarketLens errors into ``ToolError`` so clients see the real message."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except MarketLensError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def _period(value: str) -> Period:
    if value not in PERIODS:
        raise ToolError(f"period must be one of {', '.join(PERIODS)}, got {value!r}")
    return value  # type: ignore[return-value]


@server.tool()
@_tool_errors
def get_quote(symbol: str) -> dict[str, Any]:
    """Latest price, previous close and day change for one ticker symbol."""
    return quote_to_dict(provider_factory().get_quote(symbol))


@server.tool()
@_tool_errors
def analyze_ticker(symbol: str, period: str = "1y") -> dict[str, Any]:
    """Return, volatility, drawdown, Sharpe, SMA 50/200, RSI and fundamentals for one symbol.

    ``period`` is the history window: 1mo, 3mo, 6mo, 1y, 2y, 5y or max.
    """
    return summarize(symbol, provider_factory(), _period(period)).to_dict()


@server.tool()
@_tool_errors
def compare_tickers(symbols: list[str], period: str = "1y") -> dict[str, Any]:
    """Side-by-side summaries for two or more symbols plus the correlation of daily returns."""
    if len(symbols) < 2:
        raise ToolError("provide at least two symbols to compare")
    return compare(symbols, provider_factory(), _period(period)).to_dict()


@server.tool()
@_tool_errors
def portfolio_summary(path: str) -> dict[str, Any]:
    """Value a holdings TOML file: positions, P&L, weights and day change.

    ``path`` points at a file with ``[[holdings]]`` entries of symbol, shares and cost_basis.
    """
    return value_portfolio(load_portfolio(Path(path).expanduser()), provider_factory()).to_dict()


@server.tool()
@_tool_errors
def market_brief(symbols: list[str], portfolio_path: str | None = None) -> dict[str, Any]:
    """Quotes for a watchlist with top and bottom movers, plus an optional portfolio snapshot."""
    path = Path(portfolio_path).expanduser() if portfolio_path else None
    return build_brief(provider_factory(), symbols, path).to_dict()


def main() -> None:
    """Entry point for the ``marketlens-mcp`` script: serve over stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
