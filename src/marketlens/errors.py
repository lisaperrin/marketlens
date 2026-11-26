"""Exception hierarchy for MarketLens.

Every error raised on purpose by this package derives from :class:`MarketLensError`,
so callers (the CLI, the MCP server) can catch one type and report cleanly.
"""


class MarketLensError(Exception):
    """Base class for all MarketLens errors."""


class SymbolNotFoundError(MarketLensError):
    """The data source has no data for a ticker symbol."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__(f"No market data found for symbol {symbol!r}")


class DataUnavailableError(MarketLensError):
    """The data source returned something unusable (malformed, empty or offline)."""


class HoldingsFileError(MarketLensError):
    """A portfolio holdings file is missing, unreadable or invalid."""
