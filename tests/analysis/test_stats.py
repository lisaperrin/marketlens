import math

import pandas as pd
import pytest

from marketlens.analysis.stats import (
    annualized_volatility,
    correlation_matrix,
    daily_returns,
    max_drawdown,
    sharpe_ratio,
    total_return,
)


def series(values: list[float]) -> pd.Series:
    return pd.Series(
        values, index=pd.bdate_range("2024-01-01", periods=len(values)), dtype="float64"
    )


def test_daily_returns_are_simple_percentage_changes() -> None:
    result = daily_returns(series([100, 110, 99]))
    assert result.tolist() == pytest.approx([0.10, -0.10])


def test_total_return_from_first_to_last_close() -> None:
    assert total_return(series([100, 105, 110])) == pytest.approx(0.10)


def test_total_return_of_single_point_is_zero() -> None:
    assert total_return(series([100])) == 0.0


def test_max_drawdown_is_largest_peak_to_trough_fall() -> None:
    assert max_drawdown(series([100, 120, 90, 100])) == pytest.approx(-0.25)


def test_max_drawdown_of_rising_series_is_zero() -> None:
    assert max_drawdown(series([1, 2, 3])) == 0.0


def test_constant_series_has_zero_volatility() -> None:
    assert annualized_volatility(series([50, 50, 50, 50])) == 0.0


def test_volatility_scales_with_sqrt_of_periods() -> None:
    closes = series([100, 102, 99, 103, 101, 104])
    daily_std = daily_returns(closes).std()
    assert annualized_volatility(closes) == pytest.approx(daily_std * math.sqrt(252))


def test_sharpe_ratio_of_constant_series_is_nan() -> None:
    assert math.isnan(sharpe_ratio(series([50, 50, 50])))


def test_sharpe_ratio_positive_for_rising_series() -> None:
    assert sharpe_ratio(series([100, 101, 103, 104, 106])) > 0


def test_correlation_matrix_is_over_daily_returns() -> None:
    a = series([100, 110, 99, 108.9])  # +10 %, -10 %, +10 %
    c = series([100, 90, 99, 89.1])  # -10 %, +10 %, -10 %
    matrix = correlation_matrix({"A": a, "B": a * 2, "C": c})
    assert list(matrix.index) == ["A", "B", "C"]
    assert matrix.loc["A", "A"] == pytest.approx(1.0)
    assert matrix.loc["A", "B"] == pytest.approx(1.0)
    assert matrix.loc["A", "C"] == pytest.approx(-1.0)
