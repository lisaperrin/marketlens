"""The provider protocol every data source implements."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from marketlens.data.models import Fundamentals, Interval, Period, Quote, Statements


@runtime_checkable
class MarketDataProvider(Protocol):
    """Anything that can answer the three market data questions.

    Implementations raise :class:`~marketlens.errors.SymbolNotFoundError` for unknown
    symbols and :class:`~marketlens.errors.DataUnavailableError` for malformed data.
    """

    def get_quote(self, symbol: str) -> Quote:
        """Return the latest quote for ``symbol``."""
        ...

    def get_history(
        self, symbol: str, period: Period = "1y", interval: Interval = "1d"
    ) -> pd.DataFrame:
        """Return an OHLCV frame (see :func:`~marketlens.data.models.validate_history`)."""
        ...

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        """Return headline fundamentals for ``symbol``."""
        ...

    def get_statements(self, symbol: str, years: int = 4) -> list[Statements]:
        """Return up to ``years`` annual statement records, oldest first."""
        ...
