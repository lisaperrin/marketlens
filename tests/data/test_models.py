from datetime import UTC, datetime

import pandas as pd
import pytest

from marketlens.data.models import Quote, validate_history
from marketlens.errors import DataUnavailableError


def make_quote(price: float, previous_close: float) -> Quote:
    return Quote(
        symbol="AAPL",
        name="Apple Inc.",
        price=price,
        previous_close=previous_close,
        currency="USD",
        as_of=datetime(2026, 1, 2, tzinfo=UTC),
    )


def test_change_pct_is_percentage_move_from_previous_close() -> None:
    assert make_quote(110.0, 100.0).change_pct == pytest.approx(10.0)


def test_change_pct_is_zero_when_previous_close_is_zero() -> None:
    assert make_quote(5.0, 0.0).change_pct == 0.0


def test_validate_history_rejects_missing_close_column() -> None:
    frame = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Volume": [1]},
        index=pd.to_datetime(["2024-01-02"]),
    )
    with pytest.raises(DataUnavailableError, match="Close"):
        validate_history(frame)


def test_validate_history_rejects_non_datetime_index() -> None:
    frame = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0], "Volume": [1]},
    )
    with pytest.raises(DataUnavailableError, match="DatetimeIndex"):
        validate_history(frame)


def test_validate_history_returns_frame_sorted_by_date() -> None:
    frame = pd.DataFrame(
        {
            "Open": [2.0, 1.0],
            "High": [2.0, 1.0],
            "Low": [2.0, 1.0],
            "Close": [2.0, 1.0],
            "Volume": [1, 1],
        },
        index=pd.to_datetime(["2024-01-03", "2024-01-02"]),
    )
    result = validate_history(frame)
    assert list(result["Close"]) == [1.0, 2.0]


def test_statements_is_a_frozen_record_with_optional_lines() -> None:
    from datetime import date

    from marketlens.data.models import Statements

    s = Statements(symbol="NVDA", fiscal_year_end=date(2025, 1, 26), currency="USD")
    assert s.net_ppe is None and s.capex is None and s.price_at_year_end is None
    assert s.market_cap_at_year_end is None
    full = Statements(
        symbol="NVDA",
        fiscal_year_end=date(2025, 1, 26),
        currency="USD",
        shares_outstanding=24_000_000_000,
        price_at_year_end=100.0,
    )
    assert full.market_cap_at_year_end == pytest.approx(2.4e12)
    with pytest.raises(AttributeError):
        full.capex = 1.0  # type: ignore[misc]


def test_statement_fields_tuple_matches_the_dataclass() -> None:
    import dataclasses

    from marketlens.data import STATEMENT_FIELDS
    from marketlens.data.models import Statements

    assert tuple(f.name for f in dataclasses.fields(Statements)) == STATEMENT_FIELDS
    assert STATEMENT_FIELDS[:3] == ("symbol", "fiscal_year_end", "currency")
    assert "capex" in STATEMENT_FIELDS and "employees" not in STATEMENT_FIELDS
