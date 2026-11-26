from pathlib import Path

import pytest

from marketlens.errors import HoldingsFileError
from marketlens.portfolio.holdings import Holding, Portfolio, load_portfolio

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "portfolio.example.toml"


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "portfolio.toml"
    path.write_text(text)
    return path


def test_loads_example_file() -> None:
    portfolio = load_portfolio(EXAMPLE)
    assert isinstance(portfolio, Portfolio)
    assert portfolio.base_currency == "USD"
    assert portfolio.holdings[0] == Holding(symbol="AAPL", shares=10.0, cost_basis=150.0)
    assert [h.symbol for h in portfolio.holdings] == ["AAPL", "MSFT", "VTI"]


def test_symbols_are_uppercased(tmp_path: Path) -> None:
    path = write(tmp_path, '[[holdings]]\nsymbol = "aapl"\nshares = 1\ncost_basis = 1.0\n')
    assert load_portfolio(path).holdings[0].symbol == "AAPL"


def test_base_currency_defaults_to_usd(tmp_path: Path) -> None:
    path = write(tmp_path, '[[holdings]]\nsymbol = "AAPL"\nshares = 1\ncost_basis = 1.0\n')
    assert load_portfolio(path).base_currency == "USD"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(HoldingsFileError, match="not found"):
        load_portfolio(tmp_path / "nope.toml")


def test_invalid_toml_raises(tmp_path: Path) -> None:
    with pytest.raises(HoldingsFileError, match="TOML"):
        load_portfolio(write(tmp_path, "this is = not [ toml"))


def test_missing_symbol_key_raises(tmp_path: Path) -> None:
    with pytest.raises(HoldingsFileError, match="symbol"):
        load_portfolio(write(tmp_path, "[[holdings]]\nshares = 1\ncost_basis = 1.0\n"))


def test_non_positive_shares_names_the_symbol(tmp_path: Path) -> None:
    text = '[[holdings]]\nsymbol = "AAPL"\nshares = 0\ncost_basis = 1.0\n'
    with pytest.raises(HoldingsFileError, match="AAPL"):
        load_portfolio(write(tmp_path, text))


def test_negative_cost_basis_raises(tmp_path: Path) -> None:
    text = '[[holdings]]\nsymbol = "AAPL"\nshares = 1\ncost_basis = -5\n'
    with pytest.raises(HoldingsFileError, match="cost_basis"):
        load_portfolio(write(tmp_path, text))


def test_empty_holdings_raises(tmp_path: Path) -> None:
    with pytest.raises(HoldingsFileError, match="at least one"):
        load_portfolio(write(tmp_path, 'base_currency = "USD"\n'))


def test_duplicate_symbols_are_merged_by_weighted_cost(tmp_path: Path) -> None:
    text = (
        '[[holdings]]\nsymbol = "AAPL"\nshares = 10\ncost_basis = 100\n'
        '[[holdings]]\nsymbol = "AAPL"\nshares = 10\ncost_basis = 200\n'
    )
    portfolio = load_portfolio(write(tmp_path, text))
    assert portfolio.holdings == (Holding(symbol="AAPL", shares=20.0, cost_basis=150.0),)
