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


def test_volatility_is_rendered_without_a_sign() -> None:
    text = render(summary_table(summarize("AAPL", provider(), "1mo")))
    line = next(line for line in text.splitlines() if "Annualised volatility" in line)
    assert "+" not in line and "%" in line


def test_dividend_yield_is_rendered_without_a_sign() -> None:
    text = render(summary_table(summarize("AAPL", provider(), "1mo")))
    line = next(line for line in text.splitlines() if "Dividend yield" in line)
    assert "+" not in line and "0.50%" in line


def test_summary_shows_data_timestamp() -> None:
    from marketlens.report.tables import format_as_of

    summary = summarize("AAPL", provider(), "1mo")
    text = render(summary_table(summary))
    assert format_as_of(summary.quote.as_of) in text
    assert "delayed" in text.lower()


def test_quote_table_shows_data_timestamp() -> None:
    from marketlens.report.tables import format_as_of

    quote = provider().get_quote("AAPL")
    assert format_as_of(quote.as_of) in render(quote_table([quote]))


def test_comparison_and_portfolio_show_data_timestamp() -> None:
    from marketlens.report.tables import format_as_of

    prov = provider()
    stamp = format_as_of(prov.get_quote("AAPL").as_of)
    assert stamp in render(comparison_table(compare(["AAPL", "MSFT"], prov, "1mo")))
    portfolio = Portfolio("USD", (Holding("AAPL", 10, 150.0), Holding("MSFT", 5, 300.0)))
    assert stamp in render(portfolio_table(value_portfolio(portfolio, prov)))


def test_format_as_of_uses_local_time_and_zone() -> None:
    from datetime import UTC, datetime

    from marketlens.report.tables import format_as_of

    moment = datetime(2026, 1, 2, 21, 0, tzinfo=UTC)
    expected = moment.astimezone().strftime("%Y-%m-%d %H:%M %Z")
    assert format_as_of(moment) == expected


def test_summary_timestamp_is_never_truncated_for_narrow_content() -> None:
    from marketlens.report.tables import format_as_of

    prov = FakeProvider(
        quotes={"X": make_quote("X", 10.0, 9.0)},
        histories={"X": make_history("X", [9.0, 10.0])},
        fundamentals={"X": make_fundamentals("X")},
    )
    summary = summarize("X", prov, "1mo")
    text = render(summary_table(summary))
    assert f"{format_as_of(summary.quote.as_of)} (delayed)" in text


def big_portfolio_valuation():  # type: ignore[no-untyped-def]
    prov = FakeProvider(
        quotes={
            "VWCE.DE": make_quote("VWCE.DE", 163.76, 159.21, "EUR"),
            "RHM.DE": make_quote("RHM.DE", 770.50, 738.80, "EUR"),
            "ABEA.DE": make_quote("ABEA.DE", 250.85, 242.34, "EUR"),
        }
    )
    portfolio = Portfolio(
        "EUR",
        (
            Holding("VWCE.DE", 26.60139, 144.397),
            Holding("RHM.DE", 1, 1198.941),
            Holding("ABEA.DE", 6, 207.846),
        ),
    )
    return value_portfolio(portfolio, prov)


def test_portfolio_numbers_are_never_truncated_at_100_columns() -> None:
    console = Console(width=100, record=True, force_terminal=False)
    console.print(portfolio_table(big_portfolio_valuation()))
    text = console.export_text()
    assert "…" not in text
    assert "4,356.24" in text and "1,198.94" in text and "-428.44" in text


def test_fractional_shares_show_three_decimals() -> None:
    text = render(portfolio_table(big_portfolio_valuation()))
    assert "26.601" in text and "26.60139" not in text
    assert " 6 " in text  # whole shares stay integers


def test_benchmark_rows_only_appear_when_requested() -> None:
    from marketlens.data.fake import make_history

    a = [100.0, 110.0, 104.5, 106.59, 107.6559]
    spy = [100.0, 105.0, 102.375, 103.39875, 103.9157]
    prov = FakeProvider(
        quotes={"A": make_quote("A", a[-1], a[-2]), "SPY": make_quote("SPY", spy[-1], spy[-2])},
        histories={"A": make_history("A", a), "SPY": make_history("SPY", spy)},
        fundamentals={"A": make_fundamentals("A"), "SPY": make_fundamentals("SPY")},
    )
    plain = render(summary_table(summarize("A", prov, "1y")))
    assert "Benchmark" not in plain and "SPY" not in plain
    with_bench = render(summary_table(summarize("A", prov, "1y", benchmark="SPY")))
    assert "vs SPY" in with_bench and "Beta vs SPY" in with_bench and "2.00" in with_bench
    assert "Excess return" in with_bench
    cmp_plain = render(comparison_table(compare(["A", "SPY"], prov, "1y")))
    assert "Beta" not in cmp_plain
    cmp_bench = render(comparison_table(compare(["A", "SPY"], prov, "1y", benchmark="SPY")))
    assert "Beta" in cmp_bench and "Excess" in cmp_bench


def test_portfolio_benchmark_line_only_when_present() -> None:
    from marketlens.data.fake import make_history

    a = [100.0, 110.0, 104.5, 106.59, 107.6559]
    prov = FakeProvider(
        quotes={"A": make_quote("A", 180.0, 175.0), "SPY": make_quote("SPY", 500.0, 490.0)},
        histories={"A": make_history("A", a), "SPY": make_history("SPY", a)},
    )
    portfolio = Portfolio("USD", (Holding("A", 10, 150.0),))
    plain = render(portfolio_table(value_portfolio(portfolio, prov)))
    assert "Benchmark" not in plain
    bench = render(portfolio_table(value_portfolio(portfolio, prov, benchmark="SPY")))
    assert "Benchmark SPY" in bench and "+2.04%" in bench and "beta" in bench.lower()
