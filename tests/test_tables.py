from rich.console import Console

from marketlens.analysis.summary import compare, summarize
from marketlens.data.fake import FakeProvider, make_fundamentals, make_history, make_quote
from marketlens.portfolio.holdings import Holding, Portfolio
from marketlens.portfolio.valuation import value_portfolio
from marketlens.report.tables import comparison_table, portfolio_table, quote_table, summary_table


def render(renderable) -> str:  # type: ignore[no-untyped-def]
    console = Console(width=140, record=True, force_terminal=False)
    console.print(renderable)
    return console.export_text()


def provider() -> FakeProvider:
    return FakeProvider(
        quotes={"AAPL": make_quote("AAPL", 180.0, 175.0), "MSFT": make_quote("MSFT", 400.0, 410.0)},
        histories={
            "AAPL": make_history("AAPL", [float(100 + i) for i in range(30)]),
            "MSFT": make_history("MSFT", [float(300 - i) for i in range(30)]),
        },
        fundamentals={"AAPL": make_fundamentals("AAPL"), "MSFT": make_fundamentals("MSFT")},
    )


def test_quote_table_shows_symbol_price_and_change() -> None:
    text = render(quote_table([provider().get_quote("AAPL")]))
    assert "AAPL" in text and "180.00" in text and "+2.86%" in text


def test_summary_table_shows_key_stats() -> None:
    text = render(summary_table(summarize("AAPL", provider(), "1mo")))
    assert "Total return" in text and "Max drawdown" in text and "Technology" in text


def test_comparison_table_lists_both_symbols_and_correlation() -> None:
    text = render(comparison_table(compare(["AAPL", "MSFT"], provider(), "1mo")))
    assert "AAPL" in text and "MSFT" in text and "Correlation" in text


def test_portfolio_table_shows_positions_and_total() -> None:
    portfolio = Portfolio("USD", (Holding("AAPL", 10, 150.0), Holding("MSFT", 5, 300.0)))
    text = render(portfolio_table(value_portfolio(portfolio, provider())))
    assert "AAPL" in text and "3,800.00" in text and "Total" in text
