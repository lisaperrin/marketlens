"""Command-line interface. Run ``marketlens --help``."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, get_args

import typer
from rich.console import Console

from marketlens import __version__
from marketlens.analysis.summary import compare as compare_symbols
from marketlens.analysis.summary import summarize
from marketlens.data.cache import CachedProvider
from marketlens.data.models import PERIODS, Period
from marketlens.data.provider import MarketDataProvider
from marketlens.data.yfinance_provider import YFinanceProvider
from marketlens.errors import MarketLensError
from marketlens.portfolio.holdings import load_portfolio
from marketlens.portfolio.valuation import value_portfolio
from marketlens.report.brief import build_brief, quote_to_dict
from marketlens.report.tables import (
    brief_renderable,
    comparison_table,
    portfolio_table,
    quote_table,
    summary_table,
)

app = typer.Typer(
    name="marketlens",
    help="Market research and portfolio toolkit on yfinance.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
cache_app = typer.Typer(help="Inspect or clear the local data cache.", no_args_is_help=True)
app.add_typer(cache_app, name="cache")

console = Console()
error_console = Console(stderr=True)


@dataclass
class State:
    """Global options shared by every command."""

    as_json: bool = False
    no_cache: bool = False


state = State()


def get_cache() -> CachedProvider:
    """Return the on-disk cache wrapping the live provider."""
    return CachedProvider(YFinanceProvider())


def get_provider(no_cache: bool = False) -> MarketDataProvider:
    """Return the provider commands should use (patched in tests)."""
    return YFinanceProvider() if no_cache else get_cache()


def _version(value: bool) -> None:
    if value:
        console.print(f"marketlens {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    as_json: Annotated[
        bool, typer.Option("--json", help="Print machine-readable JSON instead of tables.")
    ] = False,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="Bypass the local cache and hit Yahoo directly.")
    ] = False,
    _: Annotated[
        bool | None,
        typer.Option("--version", callback=_version, is_eager=True, help="Show the version."),
    ] = None,
) -> None:
    """Market research and portfolio toolkit on yfinance."""
    state.as_json = as_json
    state.no_cache = no_cache


def _emit(data: Any, renderable: Any) -> None:
    if state.as_json:
        typer.echo(json.dumps(data, indent=2, default=str))
    else:
        console.print(renderable)


def _parse_period(value: str) -> Period:
    if value not in PERIODS:
        raise typer.BadParameter(f"must be one of {', '.join(PERIODS)}")
    return value  # type: ignore[return-value]


PeriodOption = Annotated[
    str,
    typer.Option("--period", "-p", help=f"History window: {', '.join(get_args(Period))}."),
]


BenchmarkOption = Annotated[
    str | None,
    typer.Option(
        "--benchmark", "-b", help="Compare against this symbol (e.g. SPY, VWCE.DE) over the period."
    ),
]


def _run(action: Any) -> None:
    """Call ``action`` and turn MarketLens errors into a one-line failure, exit code 1."""
    try:
        action()
    except MarketLensError as exc:
        error_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def quote(symbols: Annotated[list[str], typer.Argument(help="Ticker symbols.")]) -> None:
    """Latest price and day change for one or more symbols."""

    def action() -> None:
        provider = get_provider(state.no_cache)
        quotes = [provider.get_quote(s) for s in symbols]
        _emit([quote_to_dict(q) for q in quotes], quote_table(quotes))

    _run(action)


@app.command()
def analyze(
    symbol: Annotated[str, typer.Argument(help="Ticker symbol.")],
    period: PeriodOption = "1y",
    benchmark: BenchmarkOption = None,
) -> None:
    """Return, risk, trend indicators and fundamentals for one symbol."""
    window = _parse_period(period)

    def action() -> None:
        summary = summarize(symbol, get_provider(state.no_cache), window, benchmark)
        _emit(summary.to_dict(), summary_table(summary))

    _run(action)


@app.command()
def compare(
    symbols: Annotated[list[str], typer.Argument(help="Two or more ticker symbols.")],
    period: PeriodOption = "1y",
    benchmark: BenchmarkOption = None,
) -> None:
    """Side-by-side statistics and return correlation for several symbols."""
    if len(symbols) < 2:
        raise typer.BadParameter("provide at least two symbols to compare")
    window = _parse_period(period)

    def action() -> None:
        comparison = compare_symbols(symbols, get_provider(state.no_cache), window, benchmark)
        _emit(comparison.to_dict(), comparison_table(comparison))

    _run(action)


@app.command()
def portfolio(
    path: Annotated[
        Path, typer.Argument(help="Holdings TOML file (see examples/portfolio.example.toml).")
    ] = Path("portfolio.toml"),
    benchmark: BenchmarkOption = None,
) -> None:
    """Value a holdings file: market value, P&L, weights and day change.

    --benchmark overrides the ``benchmark`` key of the holdings file.
    """

    def action() -> None:
        portfolio = load_portfolio(path)
        valuation = value_portfolio(portfolio, get_provider(state.no_cache), benchmark)
        _emit(valuation.to_dict(), portfolio_table(valuation))

    _run(action)


@app.command()
def brief(
    watchlist: Annotated[
        str | None, typer.Option("--watchlist", "-w", help="Comma-separated symbols.")
    ] = None,
    portfolio_path: Annotated[
        Path | None, typer.Option("--portfolio", help="Holdings TOML file to include.")
    ] = None,
) -> None:
    """A daily brief: movers, watchlist quotes and portfolio snapshot."""
    if watchlist is None and portfolio_path is None:
        raise typer.BadParameter("provide --watchlist and/or --portfolio")
    symbols = [s.strip() for s in (watchlist or "").split(",") if s.strip()]

    def action() -> None:
        result = build_brief(get_provider(state.no_cache), symbols, portfolio_path)
        _emit(result.to_dict(), brief_renderable(result))

    _run(action)


@cache_app.command("stats")
def cache_stats() -> None:
    """Show how many quotes, histories and fundamentals are cached."""
    cache = get_cache()
    counts = cache.stats()
    _emit(counts, f"Cache at {cache.path}: " + ", ".join(f"{k}={v}" for k, v in counts.items()))


@cache_app.command("clear")
def cache_clear() -> None:
    """Delete every cached entry."""
    removed = get_cache().clear()
    _emit({"removed": removed}, f"Removed {removed} cached entries.")


if __name__ == "__main__":
    app()
