"""Technical indicators. Each takes a ``Close`` series and returns an aligned series."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _check_window(window: int) -> None:
    if window < 1:
        raise ValueError(f"window must be a positive integer, got {window}")


def sma(close: pd.Series, window: int) -> pd.Series:
    """Simple moving average; ``NaN`` until ``window`` observations are available."""
    _check_window(window)
    return close.rolling(window=window, min_periods=window).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index using Wilder's smoothing.

    The first value is seeded with the simple average gain/loss over ``window`` changes;
    later values use ``avg = (prev * (window - 1) + current) / window``. Values before the
    seed are ``NaN``. A series with gains and no losses reads 100, one with losses and no
    gains reads 0, and a flat series (no moves at all) reads 50.
    """
    _check_window(window)
    change = close.diff().to_numpy(dtype="float64")
    gains = np.where(change > 0, change, 0.0)
    losses = np.where(change < 0, -change, 0.0)

    result = np.full(len(close), np.nan)
    if len(close) <= window:
        return pd.Series(result, index=close.index, name="RSI")

    avg_gain = float(np.mean(gains[1 : window + 1]))
    avg_loss = float(np.mean(losses[1 : window + 1]))
    result[window] = _rsi_value(avg_gain, avg_loss)
    for i in range(window + 1, len(close)):
        avg_gain = (avg_gain * (window - 1) + gains[i]) / window
        avg_loss = (avg_loss * (window - 1) + losses[i]) / window
        result[i] = _rsi_value(avg_gain, avg_loss)
    return pd.Series(result, index=close.index, name="RSI")


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0
    relative_strength = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)
