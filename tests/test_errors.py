"""Tests for the error hierarchy."""

import marketlens
from marketlens.errors import MarketLensError, SymbolNotFoundError


def test_symbol_not_found_is_a_marketlens_error() -> None:
    err = SymbolNotFoundError("ZZZZ")
    assert isinstance(err, MarketLensError)


def test_symbol_not_found_carries_symbol_and_message() -> None:
    err = SymbolNotFoundError("ZZZZ")
    assert err.symbol == "ZZZZ"
    assert "ZZZZ" in str(err)


def test_version_is_exposed() -> None:
    assert marketlens.__version__ == "0.1.0"
