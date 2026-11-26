import math

import pandas as pd
import pytest

from marketlens.analysis.indicators import rsi, sma


def series(values: list[float]) -> pd.Series:
    return pd.Series(
        values, index=pd.bdate_range("2024-01-01", periods=len(values)), dtype="float64"
    )


def test_sma_last_value_is_mean_of_window() -> None:
    result = sma(series([1, 2, 3, 4, 5]), window=3)
    assert result.iloc[-1] == pytest.approx(4.0)
    assert result.iloc[:2].isna().all()


def test_sma_window_longer_than_series_is_all_nan() -> None:
    result = sma(series([1, 2, 3, 4, 5]), window=20)
    assert result.isna().all()
    assert len(result) == 5


def test_sma_rejects_non_positive_window() -> None:
    with pytest.raises(ValueError, match="window"):
        sma(series([1, 2, 3]), window=0)


def test_rsi_of_strictly_rising_series_is_100() -> None:
    closes = [float(100 + i) for i in range(30)]
    assert rsi(series(closes), window=14).iloc[-1] == pytest.approx(100.0)


def test_rsi_of_strictly_falling_series_is_0() -> None:
    closes = [float(200 - i) for i in range(30)]
    assert rsi(series(closes), window=14).iloc[-1] == pytest.approx(0.0)


def test_rsi_of_mirrored_path_is_complement() -> None:
    closes = [100.0, 102.0, 101.0, 105.0, 103.0, 104.0, 108.0, 107.0, 110.0, 109.0]
    closes += [111.0, 110.0, 113.0, 112.0, 115.0, 114.0, 118.0, 116.0, 119.0, 121.0]
    original = series(closes)
    mirrored = 2 * closes[0] - original
    assert rsi(mirrored, window=14).iloc[-1] == pytest.approx(
        100.0 - rsi(original, window=14).iloc[-1]
    )


def test_rsi_matches_hand_computed_wilder_value() -> None:
    # window=2: seed = mean of first two changes, then Wilder smoothing.
    # changes: +1, -1, +2  -> seed gain 0.5, loss 0.5; then gain (0.5*1+2)/2=1.25, loss 0.25
    # RS = 5 -> RSI = 100 - 100/6
    result = rsi(series([10.0, 11.0, 10.0, 12.0]), window=2)
    assert result.iloc[-1] == pytest.approx(100 - 100 / 6)


def test_rsi_is_nan_before_window_fills() -> None:
    result = rsi(series([float(100 + i) for i in range(10)]), window=14)
    assert all(math.isnan(v) for v in result)
