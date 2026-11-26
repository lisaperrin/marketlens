from pathlib import Path

import pytest

from marketlens.data.cache import TTL_FUNDAMENTALS, TTL_HISTORY, TTL_QUOTE, CachedProvider
from marketlens.data.fake import FakeProvider, make_fundamentals, make_history, make_quote


class CountingProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__(
            quotes={"AAPL": make_quote("AAPL", 180.0, 175.0)},
            histories={"AAPL": make_history("AAPL", [170.0, 180.0])},
            fundamentals={"AAPL": make_fundamentals("AAPL")},
        )
        self.calls = 0

    def get_quote(self, symbol: str):  # type: ignore[no-untyped-def]
        self.calls += 1
        return super().get_quote(symbol)

    def get_history(self, symbol: str, period="1y", interval="1d"):  # type: ignore[no-untyped-def]
        self.calls += 1
        return super().get_history(symbol, period, interval)

    def get_fundamentals(self, symbol: str):  # type: ignore[no-untyped-def]
        self.calls += 1
        return super().get_fundamentals(symbol)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def setup(tmp_path: Path) -> tuple[CountingProvider, CachedProvider, FakeClock]:
    inner = CountingProvider()
    clock = FakeClock()
    cached = CachedProvider(inner, path=tmp_path / "cache.db", clock=clock)
    return inner, cached, clock


def test_ttls_match_design() -> None:
    assert (TTL_QUOTE, TTL_HISTORY, TTL_FUNDAMENTALS) == (900, 3600, 86400)


def test_second_quote_call_is_served_from_cache(setup) -> None:  # type: ignore[no-untyped-def]
    inner, cached, _ = setup
    first = cached.get_quote("AAPL")
    second = cached.get_quote("AAPL")
    assert first == second
    assert inner.calls == 1


def test_history_round_trips_through_cache(setup) -> None:  # type: ignore[no-untyped-def]
    inner, cached, _ = setup
    first = cached.get_history("AAPL", period="1y")
    second = cached.get_history("AAPL", period="1y")
    assert inner.calls == 1
    assert list(second.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert second["Close"].tolist() == first["Close"].tolist()
    assert second.index.equals(first.index)


def test_different_period_is_a_different_cache_key(setup) -> None:  # type: ignore[no-untyped-def]
    inner, cached, _ = setup
    cached.get_history("AAPL", period="1y")
    cached.get_history("AAPL", period="5y")
    assert inner.calls == 2


def test_quote_expires_after_ttl(setup) -> None:  # type: ignore[no-untyped-def]
    inner, cached, clock = setup
    cached.get_quote("AAPL")
    clock.now += TTL_QUOTE - 1
    cached.get_quote("AAPL")
    assert inner.calls == 1
    clock.now += 2
    cached.get_quote("AAPL")
    assert inner.calls == 2


def test_fundamentals_round_trip_and_ttl(setup) -> None:  # type: ignore[no-untyped-def]
    inner, cached, clock = setup
    first = cached.get_fundamentals("AAPL")
    clock.now += TTL_FUNDAMENTALS - 1
    assert cached.get_fundamentals("AAPL") == first
    assert inner.calls == 1


def test_corrupted_payload_is_treated_as_miss(setup, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    import sqlite3

    inner, cached, _ = setup
    cached.get_quote("AAPL")
    with sqlite3.connect(tmp_path / "cache.db") as conn:
        conn.execute("UPDATE entries SET payload = 'not json'")
    quote = cached.get_quote("AAPL")
    assert quote.price == 180.0
    assert inner.calls == 2


def test_clear_returns_number_of_rows_removed(setup) -> None:  # type: ignore[no-untyped-def]
    _, cached, _ = setup
    cached.get_quote("AAPL")
    cached.get_history("AAPL")
    assert cached.stats() == {"quote": 1, "history": 1, "fundamentals": 0}
    assert cached.clear() == 2
    assert cached.stats() == {"quote": 0, "history": 0, "fundamentals": 0}


def test_errors_from_inner_provider_are_not_cached(setup) -> None:  # type: ignore[no-untyped-def]
    from marketlens.errors import SymbolNotFoundError

    inner, cached, _ = setup
    with pytest.raises(SymbolNotFoundError):
        cached.get_quote("ZZZZ")
    with pytest.raises(SymbolNotFoundError):
        cached.get_quote("ZZZZ")
    assert inner.calls == 2
