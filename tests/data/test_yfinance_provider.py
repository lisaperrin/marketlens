from types import SimpleNamespace

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
