"""Immutable data models shared by every provider and consumer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, get_args

import pandas as pd

from marketlens.errors import DataUnavailableError

Period = Literal["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]
Interval = Literal["1d", "1wk", "1mo"]

PERIODS: tuple[str, ...] = get_args(Period)
INTERVALS: tuple[str, ...] = get_args(Interval)

OHLCV_COLUMNS: tuple[str, ...] = ("Open", "High", "Low", "Close", "Volume")


@dataclass(frozen=True, slots=True)
class Quote:
    """A point-in-time price for one symbol."""

    symbol: str
    name: str
    price: float
    previous_close: float
    currency: str
    as_of: datetime

    @property
    def change(self) -> float:
        """Absolute move since the previous close."""
        return self.price - self.previous_close

    @property
    def change_pct(self) -> float:
        """Percentage move since the previous close (``10.0`` means +10 %)."""
        if self.previous_close == 0:
            return 0.0
        return (self.price / self.previous_close - 1.0) * 100.0


@dataclass(frozen=True, slots=True)
class Fundamentals:
    """Headline valuation and classification data. Every field may be missing."""

    symbol: str
    market_cap: int | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    sector: str | None = None
    industry: str | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None


def validate_history(frame: pd.DataFrame) -> pd.DataFrame:
    """Check a price history frame and return it normalised.

    The result has a ``DatetimeIndex`` sorted ascending and exactly the OHLCV columns
    in canonical order.

    Raises:
        DataUnavailableError: if a required column is missing or the index is not datetime.
    """
    missing = [column for column in OHLCV_COLUMNS if column not in frame.columns]
    if missing:
        raise DataUnavailableError(f"Price history is missing columns: {', '.join(missing)}")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise DataUnavailableError("Price history must be indexed by a DatetimeIndex")
    return frame.loc[:, list(OHLCV_COLUMNS)].sort_index()
