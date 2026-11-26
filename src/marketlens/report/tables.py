"""Rich renderables for the terminal."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from rich import box
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from marketlens.alerts.engine import Alert
from marketlens.analysis.summary import Comparison, TickerSummary
from marketlens.data.models import Quote
from marketlens.portfolio.valuation import PortfolioValuation
from marketlens.report.brief import Brief


def format_as_of(moment: datetime) -> str:
    """Render a data timestamp in the user's local time zone, e.g. ``2026-11-26 17:16 CET``."""
    return moment.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def _as_of_caption(moment: datetime) -> str:
    return f"Data as of {format_as_of(moment)} · delayed market data"


def _table(title: str, **kwargs: object) -> Table:
    """A compact table whose columns are never collapsed into ellipses."""
    return Table(title=title, box=box.SIMPLE_HEAD, pad_edge=False, **kwargs)  # type: ignore[arg-type]


def _col(table: Table, header: str, **kwargs: object) -> None:
    table.add_column(header, no_wrap=True, **kwargs)  # type: ignore[arg-type]


def _shares(value: float) -> str:
    return f"{value:g}" if value == int(value) else f"{value:.3f}".rstrip("0")


def _money(value: float) -> str:
    return f"{value:,.2f}"


def _pct(value: float | None, *, fraction: bool = False) -> Text:
    """Format a percentage with a sign and colour. ``fraction`` scales 0.10 to 10 %."""
    if value is None:
        return Text("—", style="dim")
    shown = value * 100.0 if fraction else value
    style = "green" if shown > 0 else "red" if shown < 0 else "default"
    return Text(f"{shown:+.2f}%", style=style)


def _unsigned_pct(value: float | None, *, fraction: bool = False) -> str:
    """Format a magnitude such as volatility: no sign, no colour."""
    if value is None:
        return "—"
    return f"{value * 100.0 if fraction else value:.2f}%"


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
    quotes = list(quotes)
    table = _table("Quotes")
    if quotes:
        table.caption = _as_of_caption(max(q.as_of for q in quotes))
    _col(table, "Symbol", style="bold")
    table.add_column("Name")
    _col(table, "Price", justify="right")
    _col(table, "Change", justify="right")
    _col(table, "Change %", justify="right")
    _col(table, "Ccy")
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
        ("Annualised volatility", _unsigned_pct(summary.annualized_volatility, fraction=True)),
        ("Max drawdown", _pct(summary.max_drawdown, fraction=True)),
        ("Sharpe ratio", _num(summary.sharpe_ratio)),
        ("SMA 50 / 200", _pair(summary.sma_50, summary.sma_200)),
        ("RSI 14", _num(summary.rsi_14, 1)),
        ("Market cap", _big(fundamentals.market_cap)),
        ("P/E trailing / forward", _pair(fundamentals.trailing_pe, fundamentals.forward_pe)),
        ("Dividend yield", _unsigned_pct(fundamentals.dividend_yield)),
        ("Beta", _num(fundamentals.beta)),
        ("52-week range", _pair(fundamentals.fifty_two_week_low, fundamentals.fifty_two_week_high)),
        ("Sector / industry", f"{fundamentals.sector or '—'} / {fundamentals.industry or '—'}"),
    ]
    for label, value in rows:
        table.add_row(label, value)
    if summary.signals:
        table.add_section()
        table.add_row("Signals", Text("\n".join(summary.signals), style="yellow"))
    if (bench := summary.benchmark) is not None:
        table.add_section()
        table.add_row(
            f"vs {bench.symbol} ({bench.period})", _pct(bench.benchmark_return, fraction=True)
        )
        table.add_row("Excess return", _pct(bench.excess_return, fraction=True))
        table.add_row(f"Beta vs {bench.symbol}", _num(bench.beta))
    table.add_section()
    table.add_row("Data as of", Text(f"{format_as_of(quote.as_of)} (delayed)", style="dim"))
    return Panel(table, title=f"[bold]{quote.symbol}[/bold] · {quote.name}", expand=False)


def indicator_table(summary: TickerSummary) -> Table:
    """EMA, MACD and Bollinger Band values; shown with ``analyze --indicators``."""
    snap = summary.indicators
    table = _table(f"Indicators · {summary.symbol}")
    _col(table, "Indicator", style="dim")
    _col(table, "Value", justify="right")
    _col(table, "Note", style="dim")
    last = summary.last_close
    table.add_row("EMA 20", _num(snap.ema_20), _above_below(last, snap.ema_20))
    table.add_row("MACD (12, 26)", _num(snap.macd, 3), "")
    table.add_row("MACD signal (9)", _num(snap.macd_signal, 3), "")
    table.add_row(
        "MACD histogram",
        _num(snap.macd_histogram, 3),
        ""
        if snap.macd_histogram is None
        else ("bullish" if snap.macd_histogram > 0 else "bearish"),
    )
    table.add_row("Bollinger upper (20, 2 std)", _num(snap.bb_upper), "")
    table.add_row("Bollinger middle", _num(snap.bb_middle), _above_below(last, snap.bb_middle))
    table.add_row("Bollinger lower", _num(snap.bb_lower), "")
    return table


def _above_below(price: float, level: float | None) -> str:
    if level is None:
        return ""
    return "price above" if price > level else "price below"


def comparison_table(comparison: Comparison) -> RenderableType:
    """Side-by-side stats, followed by the return-correlation matrix."""
    with_benchmark = any(s.benchmark is not None for s in comparison.summaries)
    stats = _table("Comparison")
    _col(stats, "Symbol", style="bold")
    headers = ["Price", "Return", "Volatility", "Max DD", "Sharpe", "RSI", "P/E"]
    if with_benchmark:
        headers += ["Excess", "Beta"]
    for header in headers:
        _col(stats, header, justify="right")
    for s in comparison.summaries:
        cells: list[RenderableType] = [
            s.symbol,
            _money(s.quote.price),
            _pct(s.total_return, fraction=True),
            _unsigned_pct(s.annualized_volatility, fraction=True),
            _pct(s.max_drawdown, fraction=True),
            _num(s.sharpe_ratio),
            _num(s.rsi_14, 1),
            _num(s.fundamentals.trailing_pe),
        ]
        if with_benchmark:
            bench = s.benchmark
            cells += [
                _pct(bench.excess_return, fraction=True) if bench else Text("—", style="dim"),
                _num(bench.beta) if bench else "—",
            ]
        stats.add_row(*cells)
    if with_benchmark:
        names = {s.benchmark.symbol for s in comparison.summaries if s.benchmark}
        stats.title = f"Comparison · vs {', '.join(sorted(names))}"

    if comparison.summaries:
        stats.caption = _as_of_caption(max(s.quote.as_of for s in comparison.summaries))
    matrix = _table("Correlation of daily returns")
    _col(matrix, "", style="bold")
    symbols = [str(c) for c in comparison.correlation.columns]
    for symbol in symbols:
        _col(matrix, symbol, justify="right")
    values = comparison.correlation.to_numpy(dtype="float64")
    for i, row in enumerate(symbols):
        matrix.add_row(row, *(_num(float(value)) for value in values[i]))
    return Group(stats, matrix)


def portfolio_table(valuation: PortfolioValuation) -> Table:
    """Positions with P&L and weights, plus a totals row."""
    caption = _as_of_caption(valuation.as_of)
    if (bench := valuation.benchmark) is not None:
        beta_text = "n/a" if bench.weighted_beta is None else f"{bench.weighted_beta:.2f}"
        caption = (
            f"Benchmark {bench.symbol}: day {bench.day_change_pct:+.2f}% · "
            f"portfolio beta {beta_text} ({bench.period})\n{caption}"
        )
    table = _table(f"Portfolio ({valuation.base_currency})", caption=caption)
    _col(table, "Symbol", style="bold")
    for header in ("Shares", "Price", "Value", "Cost", "P&L", "P&L %", "Day %", "Weight"):
        _col(table, header, justify="right")
    for p in valuation.positions:
        table.add_row(
            p.symbol,
            _shares(p.shares),
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


def alerts_table(alerts: list[Alert], symbols: list[str]) -> RenderableType:
    """One row per fired alert, or a one-line all-clear."""
    if not alerts:
        return Text(f"No alerts for {len(symbols)} symbol(s).", style="green")
    table = _table(f"Alerts · {len(alerts)} fired across {len(symbols)} symbol(s)")
    _col(table, "Symbol", style="bold")
    _col(table, "Kind")
    table.add_column("Message")
    for alert in alerts:
        table.add_row(alert.symbol, alert.kind, alert.message)
    return table
