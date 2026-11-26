"""A daily brief: watchlist quotes, biggest movers and an optional portfolio snapshot."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlens.data.models import Quote
from marketlens.data.provider import MarketDataProvider
from marketlens.portfolio.holdings import load_portfolio
from marketlens.portfolio.valuation import PortfolioValuation, value_portfolio


@dataclass(frozen=True, slots=True)
class Brief:
    """Everything the ``brief`` command and ``market_brief`` MCP tool report."""

    generated_at: datetime
    watchlist: tuple[Quote, ...]
    portfolio: PortfolioValuation | None

    @property
    def top_mover(self) -> Quote | None:
        """Watchlist quote with the largest percentage gain (or smallest loss)."""
        return max(self.watchlist, key=lambda q: q.change_pct, default=None)

    @property
    def bottom_mover(self) -> Quote | None:
        """Watchlist quote with the largest percentage loss (or smallest gain)."""
        return min(self.watchlist, key=lambda q: q.change_pct, default=None)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable mapping."""
        return {
            "generated_at": self.generated_at.isoformat(),
            "watchlist": [quote_to_dict(q) for q in self.watchlist],
            "movers": {
                "top": quote_to_dict(self.top_mover) if self.top_mover else None,
                "bottom": quote_to_dict(self.bottom_mover) if self.bottom_mover else None,
            },
            "portfolio": self.portfolio.to_dict() if self.portfolio else None,
        }


def quote_to_dict(quote: Quote) -> dict[str, Any]:
    """Serialise a quote including its derived change fields."""
    return {
        "symbol": quote.symbol,
        "name": quote.name,
        "price": quote.price,
        "previous_close": quote.previous_close,
        "change": quote.change,
        "change_pct": quote.change_pct,
        "currency": quote.currency,
        "as_of": quote.as_of.isoformat(),
    }


def build_brief(
    provider: MarketDataProvider,
    watchlist: list[str] | None = None,
    portfolio_path: Path | None = None,
) -> Brief:
    """Quote the watchlist and value the portfolio if a holdings file is given."""
    valuation = None
    if portfolio_path is not None:
        # A brief is a quote scan: never pull per-holding histories for the file's benchmark.
        portfolio = dataclasses.replace(load_portfolio(portfolio_path), benchmark=None)
        valuation = value_portfolio(portfolio, provider)
    quotes = tuple(provider.get_quote(symbol.upper()) for symbol in watchlist or [])
    return Brief(generated_at=datetime.now(tz=UTC), watchlist=quotes, portfolio=valuation)
