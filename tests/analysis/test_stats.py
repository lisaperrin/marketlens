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


def test_volatility_known_answer() -> None:
    # returns +10 %, -10 %: sample std = sqrt(0.02); annualised = sqrt(0.02) * sqrt(252)
    assert annualized_volatility(series([100, 110, 99])) == pytest.approx(2.2449944, abs=1e-6)


def test_sharpe_ratio_known_answer() -> None:
    # returns +0.1, -0.1, +0.1: mean 1/30, sample std sqrt(0.04/3); ratio * sqrt(252)
    assert sharpe_ratio(series([100, 110, 99, 108.9])) == pytest.approx(4.5825757, abs=1e-6)


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


# --- benchmark statistics ---------------------------------------------------------------

from marketlens.analysis.stats import aligned_total_returns, beta  # noqa: E402


def closes_from_returns(start: float, returns: list[float], first_day: str = "2024-01-01"):  # type: ignore[no-untyped-def]
    values = [start]
    for r in returns:
        values.append(values[-1] * (1 + r))
    index = pd.bdate_range(first_day, periods=len(values))
    return pd.Series(values, index=index, dtype="float64")


def test_beta_against_itself_is_one() -> None:
    a = closes_from_returns(100, [0.1, -0.05, 0.02, 0.01])
    assert beta(a, a) == pytest.approx(1.0)


def test_beta_of_doubled_returns_is_two() -> None:
    returns = [0.1, -0.05, 0.02, 0.01]
    a = closes_from_returns(100, returns)
    b = closes_from_returns(100, [2 * r for r in returns])
    assert beta(b, a) == pytest.approx(2.0)


def test_beta_against_constant_benchmark_is_none() -> None:
    a = closes_from_returns(100, [0.1, -0.05, 0.02])
    flat = closes_from_returns(50, [0.0, 0.0, 0.0])
    assert beta(a, flat) is None


def test_beta_needs_at_least_three_shared_returns() -> None:
    a = closes_from_returns(100, [0.1, -0.05, 0.02, 0.01])
    short = closes_from_returns(100, [0.1, -0.05], first_day="2024-01-03")
    assert beta(a, short) is None


def test_aligned_total_returns_use_overlap_only() -> None:
    a = closes_from_returns(100, [0.1, 0.1, 0.1, 0.1])  # 5 days from Jan 1
    b = closes_from_returns(100, [0.5, 0.5], first_day="2024-01-03")  # 3 days from Jan 3
    ra, rb = aligned_total_returns(a, b)
    # overlap is Jan 3..Jan 5: a goes 121 -> 146.41 (+21 %), b goes 100 -> 225 (+125 %)
    assert ra == pytest.approx(0.21)
    assert rb == pytest.approx(1.25)
