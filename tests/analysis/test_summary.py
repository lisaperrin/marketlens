import pytest

from marketlens.analysis.summary import TickerSummary, compare, summarize
from marketlens.data.fake import FakeProvider, make_fundamentals, make_history, make_quote
from marketlens.errors import SymbolNotFoundError


def provider_with(symbol: str, closes: list[float]) -> FakeProvider:
    return FakeProvider(
        quotes={symbol: make_quote(symbol, closes[-1], closes[-2])},
        histories={symbol: make_history(symbol, closes)},
        fundamentals={symbol: make_fundamentals(symbol)},
    )


def test_summarize_combines_quote_fundamentals_and_stats() -> None:
    closes = [float(100 + i) for i in range(260)]
    summary = summarize("AAPL", provider_with("AAPL", closes), period="1y")
    assert isinstance(summary, TickerSummary)
    assert summary.quote.symbol == "AAPL"
    assert summary.fundamentals.sector == "Technology"
    assert summary.period == "1y"
    assert summary.last_close == 359.0
    assert summary.total_return == pytest.approx(2.59)
    assert summary.sma_50 == pytest.approx(sum(closes[-50:]) / 50)
    assert summary.sma_200 == pytest.approx(sum(closes[-200:]) / 200)
    assert summary.rsi_14 == pytest.approx(100.0)
    assert summary.max_drawdown == 0.0


def test_summarize_with_short_history_leaves_long_indicators_none() -> None:
    summary = summarize("AAPL", provider_with("AAPL", [100.0, 101.0, 102.0, 103.0, 104.0]))
    assert summary.sma_50 is None
    assert summary.sma_200 is None
    assert summary.rsi_14 is None
    assert summary.total_return == pytest.approx(0.04)


def test_summarize_unknown_symbol_raises() -> None:
    with pytest.raises(SymbolNotFoundError):
        summarize("ZZZZ", FakeProvider())


def test_summary_to_dict_is_json_friendly() -> None:
    summary = summarize("AAPL", provider_with("AAPL", [100.0, 110.0]))
    data = summary.to_dict()
    assert data["symbol"] == "AAPL"
    assert data["quote"]["price"] == 110.0
    assert isinstance(data["quote"]["as_of"], str)
    assert data["total_return"] == pytest.approx(0.10)
    assert data["sma_200"] is None


def test_compare_returns_summaries_and_correlation() -> None:
    a, b = [100.0], [100.0]
    for i in range(29):
        a.append(a[-1] * (1.1 if i % 2 == 0 else 0.9))
        b.append(b[-1] * (0.9 if i % 2 == 0 else 1.1))
    provider = FakeProvider(
        quotes={"A": make_quote("A", a[-1], a[-2]), "B": make_quote("B", b[-1], b[-2])},
        histories={"A": make_history("A", a), "B": make_history("B", b)},
        fundamentals={"A": make_fundamentals("A"), "B": make_fundamentals("B")},
    )
    comparison = compare(["A", "B"], provider, period="1y")
    assert [s.quote.symbol for s in comparison.summaries] == ["A", "B"]
    assert comparison.correlation.loc["A", "B"] == pytest.approx(-1.0)
    data = comparison.to_dict()
    assert data["correlation"]["A"]["B"] == pytest.approx(-1.0)
    assert data["summaries"][0]["symbol"] == "A"
