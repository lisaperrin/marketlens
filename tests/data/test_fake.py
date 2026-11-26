import pytest

from marketlens.data.fake import FakeProvider, make_history, make_quote
from marketlens.errors import SymbolNotFoundError


def test_make_history_builds_ohlcv_frame_from_closes() -> None:
    frame = make_history("AAPL", [100.0, 101.0, 102.0])
    assert list(frame.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(frame) == 3
    assert frame["Close"].iloc[-1] == 102.0
    assert frame.index.is_monotonic_increasing


def test_fake_provider_serves_registered_data() -> None:
    provider = FakeProvider(
        quotes={"AAPL": make_quote("AAPL", 180.0, 175.0)},
        histories={"AAPL": make_history("AAPL", [170.0, 180.0])},
    )
    assert provider.get_quote("AAPL").price == 180.0
    assert provider.get_history("AAPL")["Close"].iloc[-1] == 180.0


def test_fake_provider_is_case_insensitive() -> None:
    provider = FakeProvider(quotes={"AAPL": make_quote("AAPL", 180.0, 175.0)})
    assert provider.get_quote("aapl").symbol == "AAPL"


def test_fake_provider_raises_for_unknown_symbol() -> None:
    provider = FakeProvider()
    with pytest.raises(SymbolNotFoundError, match="ZZZZ"):
        provider.get_quote("ZZZZ")
    with pytest.raises(SymbolNotFoundError):
        provider.get_history("ZZZZ")
    with pytest.raises(SymbolNotFoundError):
        provider.get_fundamentals("ZZZZ")


def test_make_statements_builds_oldest_first_records() -> None:
    from marketlens.data.fake import make_statements

    statements = make_statements("NVDA", years=3)
    assert [s.fiscal_year_end.year for s in statements] == [2023, 2024, 2025]
    assert all(s.symbol == "NVDA" and s.currency == "USD" for s in statements)
    assert all(s.capex is not None and s.capex > 0 for s in statements)
    assert statements[-1].price_at_year_end is not None


def test_fake_provider_serves_statements() -> None:
    from marketlens.data.fake import make_statements

    provider = FakeProvider(statements={"NVDA": make_statements("NVDA", years=4)})
    assert len(provider.get_statements("nvda")) == 4
    assert len(provider.get_statements("NVDA", years=2)) == 2
    assert provider.get_statements("NVDA", years=2)[-1].fiscal_year_end.year == 2025
    with pytest.raises(SymbolNotFoundError):
        provider.get_statements("ZZZZ")
