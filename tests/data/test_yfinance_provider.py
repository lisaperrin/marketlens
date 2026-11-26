from types import SimpleNamespace
from typing import ClassVar

import pandas as pd
import pytest

from marketlens.data import yfinance_provider
from marketlens.data.fake import make_history
from marketlens.data.yfinance_provider import YFinanceProvider
from marketlens.errors import SymbolNotFoundError


class StubTicker:
    """Mimics the parts of ``yfinance.Ticker`` the provider touches."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.fast_info = {
            "lastPrice": 180.0,
            "previousClose": 175.0,
            "currency": "USD",
            "marketCap": 2_800_000_000_000,
            "yearHigh": 200.0,
            "yearLow": 150.0,
        }
        self.info = {
            "longName": "Apple Inc.",
            "trailingPE": 28.5,
            "forwardPE": 25.1,
            "dividendYield": 0.55,
            "beta": 1.2,
            "sector": "Technology",
            "industry": "Consumer Electronics",
        }
        self._history = make_history(symbol, [170.0, 175.0, 180.0])

    def history(
        self, period: str = "1y", interval: str = "1d", auto_adjust: bool = True
    ) -> pd.DataFrame:
        return self._history


class EmptyTicker(StubTicker):
    def __init__(self, symbol: str) -> None:
        super().__init__(symbol)
        self.fast_info = {}
        self.info = {}
        self._history = pd.DataFrame()


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> YFinanceProvider:
    monkeypatch.setattr(yfinance_provider, "yf", SimpleNamespace(Ticker=StubTicker))
    return YFinanceProvider()


def test_get_quote_maps_fast_info(provider: YFinanceProvider) -> None:
    quote = provider.get_quote("aapl")
    assert quote.symbol == "AAPL"
    assert quote.name == "Apple Inc."
    assert quote.price == 180.0
    assert quote.previous_close == 175.0
    assert quote.currency == "USD"
    assert quote.as_of.tzinfo is not None


def test_get_history_returns_validated_frame(provider: YFinanceProvider) -> None:
    frame = provider.get_history("AAPL", period="6mo")
    assert list(frame.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert frame["Close"].iloc[-1] == 180.0


def test_get_fundamentals_maps_info(provider: YFinanceProvider) -> None:
    fundamentals = provider.get_fundamentals("AAPL")
    assert fundamentals.market_cap == 2_800_000_000_000
    assert fundamentals.trailing_pe == 28.5
    assert fundamentals.dividend_yield == 0.55
    assert fundamentals.sector == "Technology"
    assert fundamentals.fifty_two_week_high == 200.0


def test_unknown_symbol_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yfinance_provider, "yf", SimpleNamespace(Ticker=EmptyTicker))
    provider = YFinanceProvider()
    with pytest.raises(SymbolNotFoundError, match="ZZZZ"):
        provider.get_history("ZZZZ")
    with pytest.raises(SymbolNotFoundError, match="ZZZZ"):
        provider.get_quote("ZZZZ")


class BrokenTicker(StubTicker):
    """Simulates yfinance failing at the transport layer (DNS, timeouts, HTTP 5xx)."""

    @property
    def fast_info(self):  # type: ignore[no-untyped-def, override]
        raise ConnectionError("Could not resolve host: query2.finance.yahoo.com")

    def history(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("curl: (6) Could not resolve host")


def test_transport_failures_become_data_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    from marketlens.errors import DataUnavailableError

    monkeypatch.setattr(yfinance_provider, "yf", SimpleNamespace(Ticker=BrokenTicker))
    provider = YFinanceProvider()
    with pytest.raises(DataUnavailableError, match="AAPL"):
        provider.get_quote("AAPL")
    with pytest.raises(DataUnavailableError, match="AAPL"):
        provider.get_history("AAPL")
    with pytest.raises(DataUnavailableError, match="AAPL"):
        provider.get_fundamentals("AAPL")


def test_provider_silences_yfinance_logging() -> None:
    import logging

    logging.getLogger("yfinance").setLevel(logging.NOTSET)
    YFinanceProvider()
    assert logging.getLogger("yfinance").getEffectiveLevel() >= logging.CRITICAL


class NoPreviousCloseTicker(StubTicker):
    def __init__(self, symbol: str) -> None:
        super().__init__(symbol)
        self.fast_info = {"lastPrice": 180.0, "currency": "USD"}


def test_missing_previous_close_is_not_invented(monkeypatch: pytest.MonkeyPatch) -> None:
    from marketlens.errors import DataUnavailableError

    monkeypatch.setattr(yfinance_provider, "yf", SimpleNamespace(Ticker=NoPreviousCloseTicker))
    with pytest.raises(DataUnavailableError, match="previous close"):
        YFinanceProvider().get_quote("AAPL")


# --- statements ----------------------------------------------------------------------------


def _frame(rows: dict[str, list[float | None]], columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(rows, index=pd.to_datetime(list(columns))).T


class StatementsTicker(StubTicker):
    """Three fiscal years, most recent first, the way yfinance returns them."""

    years: ClassVar[tuple[str, ...]] = ("2025-01-26", "2024-01-28", "2023-01-29")

    def __init__(self, symbol: str) -> None:
        super().__init__(symbol)
        self.info = {**self.info, "fullTimeEmployees": 36_000}
        self.balance_sheet = _frame(
            {
                "Net PPE": [6_000.0, 4_000.0, 3_800.0],
                "Total Debt": [10_000.0, 11_000.0, 12_000.0],
                "Cash And Cash Equivalents": [8_000.0, 7_000.0, 3_000.0],
                "Ordinary Shares Number": [24_000.0, 24_600.0, 24_700.0],
            },
            self.years,
        )
        self.financials = _frame(
            {
                "Research And Development": [12_000.0, 8_600.0, 7_300.0],
                "Selling General And Administration": [3_400.0, 2_600.0, 2_400.0],
            },
            self.years,
        )
        self.cashflow = _frame({"Capital Expenditure": [-3_200.0, -1_000.0, -1_800.0]}, self.years)
        closes = [float(100 + i) for i in range(800)]
        self._history = make_history(symbol, closes, start="2022-06-01")

    def history(
        self, period: str = "1y", interval: str = "1d", auto_adjust: bool = True
    ) -> pd.DataFrame:
        return self._history


def test_get_statements_maps_yfinance_frames_oldest_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yfinance_provider, "yf", SimpleNamespace(Ticker=StatementsTicker))
    statements = YFinanceProvider().get_statements("nvda", years=4)
    assert [s.fiscal_year_end.isoformat() for s in statements] == [
        "2023-01-29",
        "2024-01-28",
        "2025-01-26",
    ]
    latest = statements[-1]
    assert latest.symbol == "NVDA" and latest.currency == "USD"
    assert latest.net_ppe == 6_000.0
    assert latest.capex == 3_200.0, "capex is reported as a positive outflow"
    assert latest.rd_expense == 12_000.0 and latest.sga_expense == 3_400.0
    assert latest.total_debt == 10_000.0 and latest.cash == 8_000.0
    assert latest.shares_outstanding == 24_000.0
    # last close on or before the fiscal year end (2025-01-26 is a Sunday -> Friday 24th)
    history = StatementsTicker("NVDA")._history
    expected = float(history.loc[:"2025-01-26", "Close"].iloc[-1])
    assert latest.price_at_year_end == expected


def test_get_statements_years_limits_the_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yfinance_provider, "yf", SimpleNamespace(Ticker=StatementsTicker))
    statements = YFinanceProvider().get_statements("NVDA", years=2)
    assert [s.fiscal_year_end.year for s in statements] == [2024, 2025]


def test_get_statements_missing_lines_are_none(monkeypatch: pytest.MonkeyPatch) -> None:
    class SparseTicker(StatementsTicker):
        def __init__(self, symbol: str) -> None:
            super().__init__(symbol)
            self.financials = _frame({"Total Revenue": [1.0, 1.0, 1.0]}, self.years)
            self.cashflow = pd.DataFrame()

    monkeypatch.setattr(yfinance_provider, "yf", SimpleNamespace(Ticker=SparseTicker))
    latest = YFinanceProvider().get_statements("NVDA")[-1]
    assert latest.rd_expense is None and latest.sga_expense is None and latest.capex is None
    assert latest.net_ppe == 6_000.0


def test_get_statements_without_any_balance_sheet_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class NoStatements(StatementsTicker):
        def __init__(self, symbol: str) -> None:
            super().__init__(symbol)
            self.balance_sheet = pd.DataFrame()
            self.financials = pd.DataFrame()
            self.cashflow = pd.DataFrame()

    from marketlens.errors import DataUnavailableError

    monkeypatch.setattr(yfinance_provider, "yf", SimpleNamespace(Ticker=NoStatements))
    with pytest.raises(DataUnavailableError, match="statements"):
        YFinanceProvider().get_statements("NVDA")


def test_fundamentals_include_employees(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yfinance_provider, "yf", SimpleNamespace(Ticker=StatementsTicker))
    assert YFinanceProvider().get_fundamentals("NVDA").employees == 36_000
