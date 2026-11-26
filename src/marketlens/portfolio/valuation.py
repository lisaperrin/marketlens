"""Mark a portfolio to market and compute profit and loss."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from marketlens.analysis.stats import beta
from marketlens.data.models import Period, Quote
from marketlens.data.provider import MarketDataProvider
from marketlens.portfolio.holdings import Holding, Portfolio


@dataclass(frozen=True, slots=True)
class Position:
    """A holding valued at the latest quote."""

    symbol: str
    name: str
    shares: float
    cost_basis: float
    price: float
    currency: str
    market_value: float
    cost: float
    pnl: float
    pnl_pct: float
    day_change: float
    day_change_pct: float
    weight: float


@dataclass(frozen=True, slots=True)
class PortfolioBenchmark:
    """The portfolio against a benchmark: today's move side by side, and a weighted beta."""

    symbol: str
    period: str
    day_change_pct: float
    weighted_beta: float | None
    """Weighted average beta of the positions that have one, over ``period``."""
    beta_coverage: float
    """Share of portfolio value (0 to 1) covered by positions with a beta."""


@dataclass(frozen=True, slots=True)
class PortfolioValuation:
    """Every position plus portfolio-level totals."""

    base_currency: str
    positions: tuple[Position, ...]
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float
    day_change: float
    day_change_pct: float
    as_of: datetime
    """Timestamp of the newest quote used; quotes are delayed market data."""
    benchmark: PortfolioBenchmark | None = None
    """Present only when a benchmark was requested or set in the holdings file."""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable mapping (``as_of`` as an ISO string)."""
        data = dataclasses.asdict(self)
        data["as_of"] = self.as_of.isoformat()
        return data


def value_portfolio(
    portfolio: Portfolio,
    provider: MarketDataProvider,
    benchmark: str | None = None,
    period: Period = "1y",
) -> PortfolioValuation:
    """Fetch a quote for every holding and build the valuation.

    Weights are each position's share of total market value. Day change is computed
    against each quote's previous close. ``benchmark`` (or the portfolio's own default)
    adds a :class:`PortfolioBenchmark`; betas are computed over ``period``.
    """
    priced = [(holding, provider.get_quote(holding.symbol)) for holding in portfolio.holdings]
    total_value = sum(holding.shares * quote.price for holding, quote in priced)
    total_cost = sum(holding.shares * holding.cost_basis for holding, quote in priced)
    previous_value = sum(holding.shares * quote.previous_close for holding, quote in priced)

    positions = tuple(_position(holding, quote, total_value) for holding, quote in priced)
    benchmark_symbol = (benchmark or portfolio.benchmark or "").upper() or None
    comparison = (
        _benchmark(benchmark_symbol, positions, provider, period) if benchmark_symbol else None
    )
    return PortfolioValuation(
        base_currency=portfolio.base_currency,
        positions=positions,
        total_value=total_value,
        total_cost=total_cost,
        total_pnl=total_value - total_cost,
        total_pnl_pct=_ratio(total_value - total_cost, total_cost),
        day_change=total_value - previous_value,
        day_change_pct=_ratio(total_value - previous_value, previous_value) * 100.0,
        as_of=max(quote.as_of for _, quote in priced),
        benchmark=comparison,
    )


def _benchmark(
    symbol: str, positions: tuple[Position, ...], provider: MarketDataProvider, period: Period
) -> PortfolioBenchmark:
    bench_quote = provider.get_quote(symbol)
    bench_close = provider.get_history(symbol, period=period)["Close"]
    weighted: list[tuple[float, float]] = []
    for position in positions:
        close = provider.get_history(position.symbol, period=period)["Close"]
        position_beta = beta(close, bench_close)
        if position_beta is not None:
            weighted.append((position.weight, position_beta))
    covered = sum(weight for weight, _ in weighted)
    weighted_beta = sum(weight * b for weight, b in weighted) / covered if covered > 0 else None
    return PortfolioBenchmark(
        symbol=symbol,
        period=period,
        day_change_pct=bench_quote.change_pct,
        weighted_beta=weighted_beta,
        beta_coverage=covered,
    )


def _position(holding: Holding, quote: Quote, total_value: float) -> Position:
    market_value = holding.shares * quote.price
    cost = holding.shares * holding.cost_basis
    return Position(
        symbol=holding.symbol,
        name=quote.name,
        shares=holding.shares,
        cost_basis=holding.cost_basis,
        price=quote.price,
        currency=quote.currency,
        market_value=market_value,
        cost=cost,
        pnl=market_value - cost,
        pnl_pct=_ratio(market_value - cost, cost),
        day_change=holding.shares * quote.change,
        day_change_pct=quote.change_pct,
        weight=_ratio(market_value, total_value),
    )


def _ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator
