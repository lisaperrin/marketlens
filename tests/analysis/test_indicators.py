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


# --- EMA, MACD, Bollinger ----------------------------------------------------------------

from marketlens.analysis.indicators import bollinger, ema, macd  # noqa: E402


def test_ema_known_answer() -> None:
    # alpha = 2/(3+1) = 0.5, seeded with the first value: 1, 1.5, 2.25, 3.125, 4.0625
    result = ema(series([1, 2, 3, 4, 5]), span=3)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == pytest.approx(2.25)
    assert result.iloc[-1] == pytest.approx(4.0625)


def test_ema_rejects_non_positive_span() -> None:
    with pytest.raises(ValueError, match="span"):
        ema(series([1, 2, 3]), span=0)


def test_macd_of_constant_series_is_zero_after_warm_up() -> None:
    frame = macd(series([50.0] * 40))
    assert list(frame.columns) == ["macd", "signal", "histogram"]
    assert frame.iloc[:25].isna().all().all()
    assert frame.iloc[-1].tolist() == pytest.approx([0.0, 0.0, 0.0])


def test_macd_is_positive_when_price_accelerates() -> None:
    closes = [100.0] * 30 + [100.0 + 2 * i for i in range(1, 11)]
    frame = macd(series(closes))
    assert frame["macd"].iloc[-1] > 0
    assert frame["histogram"].iloc[-1] > 0


def test_bollinger_known_answer() -> None:
    frame = bollinger(series([1, 2, 3, 4, 5]), window=5, num_std=2.0)
    assert list(frame.columns) == ["middle", "upper", "lower"]
    assert frame["middle"].iloc[-1] == pytest.approx(3.0)
    assert frame["upper"].iloc[-1] == pytest.approx(3 + 2 * math.sqrt(2.5))
    assert frame["lower"].iloc[-1] == pytest.approx(3 - 2 * math.sqrt(2.5))
    assert frame.iloc[:4].isna().all().all()


def test_bollinger_of_constant_series_collapses_onto_price() -> None:
    frame = bollinger(series([7.0] * 25), window=20)
    assert frame.iloc[-1].tolist() == pytest.approx([7.0, 7.0, 7.0])
