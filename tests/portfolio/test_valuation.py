import pytest

from marketlens.data.fake import FakeProvider, make_quote
from marketlens.errors import SymbolNotFoundError
from marketlens.portfolio.holdings import Holding, Portfolio
from marketlens.portfolio.valuation import PortfolioValuation, Position, value_portfolio


def provider() -> FakeProvider:
    return FakeProvider(
        quotes={
            "AAPL": make_quote("AAPL", 180.0, 175.0),
            "MSFT": make_quote("MSFT", 400.0, 410.0),
        }
    )


def portfolio() -> Portfolio:
    return Portfolio(
        base_currency="USD",
        holdings=(
            Holding("AAPL", shares=10, cost_basis=150.0),
            Holding("MSFT", shares=5, cost_basis=300.0),
        ),
    )


def test_position_values_and_pnl() -> None:
    valuation = value_portfolio(portfolio(), provider())
    aapl = valuation.positions[0]
    assert isinstance(aapl, Position)
    assert aapl.price == 180.0
    assert aapl.market_value == pytest.approx(1800.0)
    assert aapl.cost == pytest.approx(1500.0)
    assert aapl.pnl == pytest.approx(300.0)
    assert aapl.pnl_pct == pytest.approx(0.20)
    assert aapl.day_change_pct == pytest.approx((180 / 175 - 1) * 100)


def test_totals_and_weights() -> None:
    valuation = value_portfolio(portfolio(), provider())
    assert isinstance(valuation, PortfolioValuation)
    assert valuation.total_value == pytest.approx(3800.0)
    assert valuation.total_cost == pytest.approx(3000.0)
    assert valuation.total_pnl == pytest.approx(800.0)
    assert valuation.total_pnl_pct == pytest.approx(800 / 3000)
    assert sum(p.weight for p in valuation.positions) == pytest.approx(1.0, abs=1e-9)
    assert valuation.positions[0].weight == pytest.approx(1800 / 3800)


def test_day_change_value_is_sum_of_position_moves() -> None:
    valuation = value_portfolio(portfolio(), provider())
    expected = 10 * (180 - 175) + 5 * (400 - 410)
    assert valuation.day_change == pytest.approx(expected)


def test_unknown_symbol_propagates() -> None:
    bad = Portfolio("USD", (Holding("ZZZZ", shares=1, cost_basis=1.0),))
    with pytest.raises(SymbolNotFoundError, match="ZZZZ"):
        value_portfolio(bad, provider())


def test_to_dict_is_json_friendly() -> None:
    data = value_portfolio(portfolio(), provider()).to_dict()
    assert data["base_currency"] == "USD"
    assert data["total_value"] == pytest.approx(3800.0)
    assert data["positions"][1]["symbol"] == "MSFT"
    assert set(data["positions"][0]) >= {
        "symbol",
        "shares",
        "price",
        "market_value",
        "pnl",
        "weight",
    }


def test_valuation_carries_latest_quote_timestamp() -> None:
    valuation = value_portfolio(portfolio(), provider())
    assert valuation.as_of == max(
        q.as_of for q in (provider().get_quote(s) for s in ("AAPL", "MSFT"))
    )
    assert isinstance(valuation.to_dict()["as_of"], str)
