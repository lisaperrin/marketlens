"""Load and validate a TOML holdings file.

Format::

    base_currency = "USD"          # optional, defaults to USD

    [[holdings]]
    symbol = "AAPL"
    shares = 10
    cost_basis = 150.00            # average price paid per share
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from marketlens.errors import HoldingsFileError


@dataclass(frozen=True, slots=True)
class Holding:
    """One line of a portfolio: how much of a symbol is owned and at what average cost."""

    symbol: str
    shares: float
    cost_basis: float


@dataclass(frozen=True, slots=True)
class Portfolio:
    """A validated set of holdings plus the currency totals are reported in."""

    base_currency: str
    holdings: tuple[Holding, ...]


def load_portfolio(path: Path) -> Portfolio:
    """Parse ``path`` into a :class:`Portfolio`.

    Symbols are upper-cased and duplicate symbols are merged into one holding with a
    share-weighted average cost basis.

    Raises:
        HoldingsFileError: if the file is missing, not valid TOML, or fails validation.
    """
    if not path.is_file():
        raise HoldingsFileError(f"Holdings file not found: {path}")
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise HoldingsFileError(f"{path} is not valid TOML: {exc}") from exc

    raw_holdings = document.get("holdings")
    if not isinstance(raw_holdings, list) or not raw_holdings:
        raise HoldingsFileError(f"{path} must contain at least one [[holdings]] entry")

    merged: dict[str, Holding] = {}
    for index, entry in enumerate(raw_holdings, start=1):
        holding = _parse_holding(entry, index)
        existing = merged.get(holding.symbol)
        merged[holding.symbol] = holding if existing is None else _merge(existing, holding)

    base_currency = str(document.get("base_currency", "USD")).upper()
    return Portfolio(base_currency=base_currency, holdings=tuple(merged.values()))


def _parse_holding(entry: Any, index: int) -> Holding:
    if not isinstance(entry, dict):
        raise HoldingsFileError(f"holdings[{index}] must be a table")
    symbol = entry.get("symbol")
    if not isinstance(symbol, str) or not symbol.strip():
        raise HoldingsFileError(f"holdings[{index}] is missing a 'symbol'")
    symbol = symbol.strip().upper()

    shares = _number(entry, "shares", symbol)
    if shares <= 0:
        raise HoldingsFileError(f"{symbol}: 'shares' must be greater than zero, got {shares}")
    cost_basis = _number(entry, "cost_basis", symbol)
    if cost_basis < 0:
        raise HoldingsFileError(f"{symbol}: 'cost_basis' cannot be negative, got {cost_basis}")
    return Holding(symbol=symbol, shares=shares, cost_basis=cost_basis)


def _number(entry: dict[str, Any], key: str, symbol: str) -> float:
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise HoldingsFileError(f"{symbol}: '{key}' must be a number")
    return float(value)


def _merge(first: Holding, second: Holding) -> Holding:
    shares = first.shares + second.shares
    cost = first.shares * first.cost_basis + second.shares * second.cost_basis
    return Holding(symbol=first.symbol, shares=shares, cost_basis=cost / shares)
