"""Immutable data models shared by every provider and consumer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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
    employees: int | None = None
    """Latest reported headcount. Yahoo has no history for it, so it lives here, not per year."""


@dataclass(frozen=True, slots=True)
class Statements:
    """Selected annual financial statement lines for one fiscal year.

    Amounts are in the reporting ``currency`` as Yahoo publishes them (usually units, not
    thousands). ``None`` means Yahoo has no such line for that year; nothing is estimated.
    ``capex`` is a positive outflow. ``total_debt`` is gross debt, not net of cash.
    """

    symbol: str
    fiscal_year_end: date
    currency: str
    net_ppe: float | None = None
    """Balance sheet: Net PPE (property, plant and equipment after depreciation)."""
    capex: float | None = None
    """Cash flow: Capital Expenditure, sign flipped to a positive number."""
    rd_expense: float | None = None
    """Income statement: Research And Development."""
    sga_expense: float | None = None
    """Income statement: Selling General And Administration."""
    total_debt: float | None = None
    """Balance sheet: Total Debt (gross)."""
    cash: float | None = None
    """Balance sheet: Cash And Cash Equivalents."""
    shares_outstanding: float | None = None
    """Balance sheet: Ordinary Shares Number at fiscal year end."""
    price_at_year_end: float | None = None
    """Last close on or before ``fiscal_year_end`` from the adjusted price history."""

    @property
    def market_cap_at_year_end(self) -> float | None:
        """``shares_outstanding * price_at_year_end`` when both are known."""
        if self.shares_outstanding is None or self.price_at_year_end is None:
            return None
        return self.shares_outstanding * self.price_at_year_end


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
