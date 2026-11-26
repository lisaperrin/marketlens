"""An in-memory provider for tests and demos. Never touches the network."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from marketlens.data.models import Fundamentals, Interval, Period, Quote, validate_history
from marketlens.errors import SymbolNotFoundError


def make_quote(symbol: str, price: float, previous_close: float, currency: str = "USD") -> Quote:
    """Build a quote with a fixed timestamp."""
    return Quote(
        symbol=symbol.upper(),
        name=f"{symbol.upper()} Inc.",
        price=price,
        previous_close=previous_close,
        currency=currency,
        as_of=datetime(2026, 1, 2, 21, 0, tzinfo=UTC),
    )


def make_fundamentals(symbol: str) -> Fundamentals:
    """Build plausible fundamentals for ``symbol``."""
    return Fundamentals(
        symbol=symbol.upper(),
        market_cap=1_000_000_000_000,
        trailing_pe=25.0,
        forward_pe=22.0,
        dividend_yield=0.5,
        beta=1.1,
        sector="Technology",
        industry="Software",
        fifty_two_week_high=200.0,
        fifty_two_week_low=120.0,
    )


def make_history(symbol: str, closes: list[float], start: str = "2024-01-01") -> pd.DataFrame:
    """Build a daily OHLCV frame from a list of closing prices.

    Open/High/Low are derived from the close so the frame is internally consistent.
    """
    index = pd.bdate_range(start=start, periods=len(closes), name="Date")
    close = pd.Series(closes, index=index, dtype="float64")
    frame = pd.DataFrame(
        {
            "Open": close.shift(1).fillna(close.iloc[0]),
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": pd.Series([1_000_000] * len(closes), index=index, dtype="int64"),
        }
    )
    frame.attrs["symbol"] = symbol.upper()
    return validate_history(frame)


class FakeProvider:
    """Serve canned data registered at construction time."""

    def __init__(
        self,
        quotes: dict[str, Quote] | None = None,
        histories: dict[str, pd.DataFrame] | None = None,
        fundamentals: dict[str, Fundamentals] | None = None,
    ) -> None:
        self._quotes = {k.upper(): v for k, v in (quotes or {}).items()}
        self._histories = {k.upper(): v for k, v in (histories or {}).items()}
        self._fundamentals = {k.upper(): v for k, v in (fundamentals or {}).items()}

    def get_quote(self, symbol: str) -> Quote:
        """Return the registered quote or raise."""
        return self._lookup(self._quotes, symbol)

    def get_history(
        self, symbol: str, period: Period = "1y", interval: Interval = "1d"
    ) -> pd.DataFrame:
        """Return the registered history (period and interval are ignored)."""
        return self._lookup(self._histories, symbol).copy()

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        """Return the registered fundamentals or raise."""
        return self._lookup(self._fundamentals, symbol)

    @staticmethod
    def _lookup[T](table: dict[str, T], symbol: str) -> T:
        try:
            return table[symbol.upper()]
        except KeyError:
            raise SymbolNotFoundError(symbol.upper()) from None
