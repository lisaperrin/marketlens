"""Rich renderables for the terminal."""

from __future__ import annotations

from collections.abc import Iterable

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from marketlens.analysis.summary import Comparison, TickerSummary
from marketlens.data.models import Quote
from marketlens.portfolio.valuation import PortfolioValuation
from marketlens.report.brief import Brief


def _money(value: float) -> str:
    return f"{value:,.2f}"


def _pct(value: float | None, *, fraction: bool = False) -> Text:
    """Format a percentage with a sign and colour. ``fraction`` scales 0.10 to 10 %."""
    if value is None:
        return Text("—", style="dim")
    shown = value * 100.0 if fraction else value
    style = "green" if shown > 0 else "red" if shown < 0 else "default"
    return Text(f"{shown:+.2f}%", style=style)


def _num(value: float | None, digits: int = 2) -> str:
    return "—" if value is None else f"{value:,.{digits}f}"


def _pair(left: float | None, right: float | None, sep: str = "/") -> str:
    return f"{_num(left)} {sep} {_num(right)}"


def _big(value: int | None) -> str:
    if value is None:
        return "—"
    for unit, size in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(value) >= size:
            return f"{value / size:.2f}{unit}"
    return f"{value:,}"


def quote_table(quotes: Iterable[Quote]) -> Table:
    """One row per quote: price, change and currency."""
    table = Table(title="Quotes", show_lines=False)
    table.add_column("Symbol", style="bold")
    table.add_column("Name")
    table.add_column("Price", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("Change %", justify="right")
    table.add_column("Ccy")
    for quote in quotes:
        table.add_row(
            quote.symbol,
            quote.name,
            _money(quote.price),
            f"{quote.change:+,.2f}",
            _pct(quote.change_pct),
            quote.currency,
        )
    return table


def summary_table(summary: TickerSummary) -> RenderableType:
    """Two-column key/value table of a ticker summary."""
    quote, fundamentals = summary.quote, summary.fundamentals
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")
    rows: list[tuple[str, RenderableType]] = [
        ("Price", f"{_money(quote.price)} {quote.currency}"),
        ("Day change", _pct(quote.change_pct)),
        (f"Total return ({summary.period})", _pct(summary.total_return, fraction=True)),
        ("Annualised volatility", _pct(summary.annualized_volatility, fraction=True)),
        ("Max drawdown", _pct(summary.max_drawdown, fraction=True)),
        ("Sharpe ratio", _num(summary.sharpe_ratio)),
        ("SMA 50 / 200", _pair(summary.sma_50, summary.sma_200)),
        ("RSI 14", _num(summary.rsi_14, 1)),
        ("Market cap", _big(fundamentals.market_cap)),
        ("P/E trailing / forward", _pair(fundamentals.trailing_pe, fundamentals.forward_pe)),
        ("Dividend yield", _pct(fundamentals.dividend_yield)),
        ("Beta", _num(fundamentals.beta)),
        ("52-week range", _pair(fundamentals.fifty_two_week_low, fundamentals.fifty_two_week_high)),
        ("Sector / industry", f"{fundamentals.sector or '—'} / {fundamentals.industry or '—'}"),
    ]
    for label, value in rows:
        table.add_row(label, value)
    return Panel(table, title=f"[bold]{quote.symbol}[/bold] · {quote.name}", expand=False)


def comparison_table(comparison: Comparison) -> RenderableType:
    """Side-by-side stats, followed by the return-correlation matrix."""
    stats = Table(title="Comparison")
    stats.add_column("Symbol", style="bold")
    stats.add_column("Price", justify="right")
    stats.add_column("Return", justify="right")
    stats.add_column("Volatility", justify="right")
    stats.add_column("Max DD", justify="right")
    stats.add_column("Sharpe", justify="right")
    stats.add_column("RSI", justify="right")
    stats.add_column("P/E", justify="right")
    for s in comparison.summaries:
        stats.add_row(
            s.symbol,
            _money(s.quote.price),
            _pct(s.total_return, fraction=True),
            _pct(s.annualized_volatility, fraction=True),
            _pct(s.max_drawdown, fraction=True),
            _num(s.sharpe_ratio),
            _num(s.rsi_14, 1),
            _num(s.fundamentals.trailing_pe),
        )

    matrix = Table(title="Correlation of daily returns")
    matrix.add_column("", style="bold")
    symbols = [str(c) for c in comparison.correlation.columns]
    for symbol in symbols:
        matrix.add_column(symbol, justify="right")
    cells = comparison.correlation.to_numpy(dtype="float64")
    for i, row in enumerate(symbols):
        matrix.add_row(row, *(_num(float(value)) for value in cells[i]))
    return Group(stats, matrix)


def portfolio_table(valuation: PortfolioValuation) -> Table:
    """Positions with P&L and weights, plus a totals row."""
    table = Table(title=f"Portfolio ({valuation.base_currency})", show_footer=False)
    table.add_column("Symbol", style="bold")
    table.add_column("Shares", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Value", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("P&L %", justify="right")
    table.add_column("Day %", justify="right")
    table.add_column("Weight", justify="right")
    for p in valuation.positions:
        table.add_row(
            p.symbol,
            f"{p.shares:g}",
            _money(p.price),
            _money(p.market_value),
            _money(p.cost),
            f"{p.pnl:+,.2f}",
            _pct(p.pnl_pct, fraction=True),
            _pct(p.day_change_pct),
            f"{p.weight * 100:.1f}%",
        )
    table.add_section()
    table.add_row(
        "Total",
        "",
        "",
        _money(valuation.total_value),
        _money(valuation.total_cost),
        f"{valuation.total_pnl:+,.2f}",
        _pct(valuation.total_pnl_pct, fraction=True),
        _pct(valuation.day_change_pct),
        "100.0%",
        style="bold",
    )
    return table


def brief_renderable(brief: Brief) -> RenderableType:
    """Headline movers, the watchlist table and the portfolio table when present."""
    parts: list[RenderableType] = []
    headline = Text()
    if brief.top_mover and brief.bottom_mover:
        headline.append("Top: ", style="dim")
        headline.append(f"{brief.top_mover.symbol} ")
        headline.append_text(_pct(brief.top_mover.change_pct))
        headline.append("   Bottom: ", style="dim")
        headline.append(f"{brief.bottom_mover.symbol} ")
        headline.append_text(_pct(brief.bottom_mover.change_pct))
    stamp = brief.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    parts.append(Panel(headline, title=f"Market brief · {stamp}", expand=False))
    if brief.watchlist:
        parts.append(quote_table(brief.watchlist))
    if brief.portfolio:
        parts.append(portfolio_table(brief.portfolio))
    return Group(*parts)
