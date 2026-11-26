"""A Model Context Protocol server exposing MarketLens to Claude and other MCP clients.

Run it over stdio with ``marketlens-mcp`` (or ``uvx --from <path to this repo> marketlens-mcp``).
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
from marketlens.alerts.engine import evaluate
from marketlens.alerts.rules import DEFAULT_RULES, load_rules
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
def analyze_ticker(
    symbol: str, period: Period = "1y", benchmark: str | None = None
) -> dict[str, Any]:
    """Return, volatility, drawdown, Sharpe, SMA 50/200, RSI and fundamentals for one symbol.

    ``period`` is the history window: 1mo, 3mo, 6mo, 1y, 2y, 5y or max. ``benchmark`` (for
    example SPY or VWCE.DE) adds the benchmark's return, the excess return and beta.
    """
    return summarize(symbol, provider_factory(), _period(period), benchmark).to_dict()


@server.tool()
@_tool_errors
def compare_tickers(
    symbols: list[str], period: Period = "1y", benchmark: str | None = None
) -> dict[str, Any]:
    """Side-by-side summaries for two or more symbols plus the correlation of daily returns.

    ``benchmark`` adds excess return and beta against that symbol to every summary.
    """
    if len(symbols) < 2:
        raise ToolError("provide at least two symbols to compare")
    return compare(symbols, provider_factory(), _period(period), benchmark).to_dict()


@server.tool()
@_tool_errors
def portfolio_summary(path: str, benchmark: str | None = None) -> dict[str, Any]:
    """Value a holdings TOML file: positions, P&L, weights and day change.

    ``path`` points at a file with ``[[holdings]]`` entries of symbol, shares and cost_basis.
    ``benchmark`` overrides the file's own ``benchmark`` key and adds the benchmark's day
    change and the portfolio's weighted beta.
    """
    portfolio = load_portfolio(Path(path).expanduser())
    return value_portfolio(portfolio, provider_factory(), benchmark).to_dict()


@server.tool()
@_tool_errors
def market_brief(symbols: list[str], portfolio_path: str | None = None) -> dict[str, Any]:
    """Quotes for a watchlist with top and bottom movers, plus an optional portfolio snapshot."""
    path = Path(portfolio_path).expanduser() if portfolio_path else None
    return build_brief(provider_factory(), symbols, path).to_dict()


@server.tool()
@_tool_errors
def check_alerts(
    symbols: list[str],
    rules_path: str | None = None,
    portfolio_path: str | None = None,
) -> dict[str, Any]:
    """Report crossed thresholds: RSI 70/30, day move of 5 % or more, Bollinger breakouts.

    ``symbols`` may be empty only when ``rules_path`` or ``portfolio_path`` supplies symbols.
    ``rules_path`` points at an alert rules TOML with per-symbol price levels and overrides;
    ``portfolio_path`` adds every holding of that file. Returns ``symbols`` (what was checked),
    ``alerts`` (empty when nothing fired; ``value`` and ``threshold`` are in natural units:
    percent for day_change_abs, RSI points, price for the rest) and ``errors`` for symbols
    whose data could not be fetched.
    """
    rules = load_rules(Path(rules_path).expanduser()) if rules_path else DEFAULT_RULES
    universe = [s.upper() for s in symbols]
    if portfolio_path:
        universe += [h.symbol for h in load_portfolio(Path(portfolio_path).expanduser()).holdings]
    if not universe and not rules.symbols:
        raise ToolError("provide symbols, or a rules_path / portfolio_path that lists some")
    return evaluate(universe, rules, provider_factory()).to_dict()


def main() -> None:
    """Entry point for the ``marketlens-mcp`` script: serve over stdio."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
