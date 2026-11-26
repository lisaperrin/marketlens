"""The live provider, backed by yfinance."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import yfinance as yf

from marketlens.data.models import Fundamentals, Interval, Period, Quote, validate_history
from marketlens.errors import DataUnavailableError, MarketLensError, SymbolNotFoundError


def _get(mapping: Mapping[str, Any] | Any, key: str) -> Any:
    """Read ``key`` from a dict-like object, returning ``None`` when absent or failing."""
    try:
        return mapping[key]
    except (KeyError, AttributeError, TypeError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(result) else result


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    return None if number is None else int(number)


def _guarded[T](symbol: str, action: Callable[[], T]) -> T:
    """Run ``action``; let MarketLens errors through, wrap anything else as unavailable data.

    yfinance raises a zoo of exception types for DNS failures, timeouts and HTTP errors.
    Callers only need to know the request could not be served.
    """
    try:
        return action()
    except MarketLensError:
        raise
    except Exception as exc:
        raise DataUnavailableError(
            f"{symbol}: could not fetch data from Yahoo Finance ({exc})"
        ) from exc


class YFinanceProvider:
    """Fetch quotes, history and fundamentals from Yahoo Finance via yfinance.

    yfinance's own logger is silenced on construction: every failure it would log is
    turned into a :class:`~marketlens.errors.MarketLensError` with a readable message.
    """

    def __init__(self) -> None:
        logging.getLogger("yfinance").setLevel(logging.CRITICAL)

    def get_quote(self, symbol: str) -> Quote:
        """Build a quote from ``Ticker.fast_info`` (cheap) plus the long name from ``info``."""
        symbol = symbol.upper()
        return _guarded(symbol, lambda: self._quote(symbol))

    def _quote(self, symbol: str) -> Quote:
        ticker = yf.Ticker(symbol)
        fast = ticker.fast_info
        price = _as_float(_get(fast, "lastPrice"))
        if price is None:
            raise SymbolNotFoundError(symbol)
        previous_close = _as_float(_get(fast, "previousClose"))
        if previous_close is None:
            raise DataUnavailableError(f"{symbol}: Yahoo Finance returned no previous close")
        info = self._safe_info(ticker)
        return Quote(
            symbol=symbol,
            name=str(_get(info, "longName") or _get(info, "shortName") or symbol),
            price=price,
            previous_close=previous_close,
            currency=str(_get(fast, "currency") or "USD"),
            as_of=datetime.now(tz=UTC),
        )

    def get_history(
        self, symbol: str, period: Period = "1y", interval: Interval = "1d"
    ) -> pd.DataFrame:
        """Return adjusted daily/weekly/monthly OHLCV bars."""
        symbol = symbol.upper()
        return _guarded(symbol, lambda: self._history(symbol, period, interval))

    def _history(self, symbol: str, period: Period, interval: Interval) -> pd.DataFrame:
        frame = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
        if frame is None or frame.empty:
            raise SymbolNotFoundError(symbol)
        try:
            return validate_history(frame)
        except DataUnavailableError as exc:
            raise DataUnavailableError(f"{symbol}: {exc}") from exc

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        """Combine ``fast_info`` (market cap, 52-week range) with ``info`` (ratios, sector)."""
        symbol = symbol.upper()
        return _guarded(symbol, lambda: self._fundamentals(symbol))

    def _fundamentals(self, symbol: str) -> Fundamentals:
        ticker = yf.Ticker(symbol)
        fast = ticker.fast_info
        info = self._safe_info(ticker)
        return Fundamentals(
            symbol=symbol,
            market_cap=_as_int(_get(fast, "marketCap")),
            trailing_pe=_as_float(_get(info, "trailingPE")),
            forward_pe=_as_float(_get(info, "forwardPE")),
            # yfinance reports dividendYield as a percentage (0.55 means 0.55 %).
            dividend_yield=_as_float(_get(info, "dividendYield")),
            beta=_as_float(_get(info, "beta")),
            sector=_get(info, "sector"),
            industry=_get(info, "industry"),
            fifty_two_week_high=_as_float(_get(fast, "yearHigh")),
            fifty_two_week_low=_as_float(_get(fast, "yearLow")),
        )

    @staticmethod
    def _safe_info(ticker: Any) -> Mapping[str, Any]:
        """``Ticker.info`` is a slow scrape that sometimes fails; degrade to empty."""
        try:
            info = ticker.info
        except Exception:
            return {}
        return info if isinstance(info, Mapping) else {}
