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
    conn = sqlite3.connect(tmp_path / "cache.db")
    with conn:
        conn.execute("UPDATE entries SET payload = 'not json'")
    conn.close()
    quote = cached.get_quote("AAPL")
    assert quote.price == 180.0
    assert inner.calls == 2


def test_clear_returns_number_of_rows_removed(setup) -> None:  # type: ignore[no-untyped-def]
    _, cached, _ = setup
    cached.get_quote("AAPL")
    cached.get_history("AAPL")
    assert cached.stats() == {"quote": 1, "history": 1, "fundamentals": 0, "statements": 0}
    assert cached.clear() == 2
    assert cached.stats() == {"quote": 0, "history": 0, "fundamentals": 0, "statements": 0}


def test_errors_from_inner_provider_are_not_cached(setup) -> None:  # type: ignore[no-untyped-def]
    from marketlens.errors import SymbolNotFoundError

    inner, cached, _ = setup
    with pytest.raises(SymbolNotFoundError):
        cached.get_quote("ZZZZ")
    with pytest.raises(SymbolNotFoundError):
        cached.get_quote("ZZZZ")
    assert inner.calls == 2


def test_every_sqlite_connection_is_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unclosed connections leak file handles and warn on Python 3.13+."""
    import sqlite3

    from marketlens.data import cache as cache_module

    opened: list[sqlite3.Connection] = []
    real_connect = sqlite3.connect

    def tracking_connect(*args, **kwargs):  # type: ignore[no-untyped-def]
        conn = real_connect(*args, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(cache_module.sqlite3, "connect", tracking_connect)
    cached = CachedProvider(CountingProvider(), path=tmp_path / "cache.db")
    cached.get_quote("AAPL")
    cached.get_quote("AAPL")
    cached.stats()
    cached.clear()
    assert len(opened) >= 4
    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            conn.execute("SELECT 1")


def test_garbage_cache_file_is_moved_aside_and_recreated(tmp_path: Path) -> None:
    path = tmp_path / "cache.db"
    path.write_bytes(b"this is not a sqlite database at all" * 10)
    inner = CountingProvider()
    cached = CachedProvider(inner, path=path)
    assert cached.get_quote("AAPL").price == 180.0
    assert cached.stats()["quote"] == 1
    assert cached.clear() == 1
    corrupt = list(tmp_path.glob("cache.db.corrupt-*"))
    assert len(corrupt) == 1, "the unreadable file is kept aside, not silently deleted"


def test_cache_file_corrupted_after_open_is_a_miss_not_a_crash(tmp_path: Path) -> None:
    path = tmp_path / "cache.db"
    inner = CountingProvider()
    cached = CachedProvider(inner, path=path)
    cached.get_quote("AAPL")
    path.write_bytes(b"garbage" * 100)
    assert cached.get_quote("AAPL").price == 180.0
    assert inner.calls == 2


def test_statements_are_cached_for_a_day(tmp_path: Path) -> None:
    from marketlens.data.cache import TTL_STATEMENTS
    from marketlens.data.fake import make_statements

    class Counting(FakeProvider):
        calls = 0

        def get_statements(self, symbol: str, years: int = 4):  # type: ignore[no-untyped-def]
            self.calls += 1
            return super().get_statements(symbol, years)

    inner = Counting(statements={"NVDA": make_statements("NVDA", years=4)})
    clock = FakeClock()
    cached = CachedProvider(inner, path=tmp_path / "cache.db", clock=clock)
    first = cached.get_statements("NVDA", years=3)
    second = cached.get_statements("NVDA", years=3)
    assert inner.calls == 1 and first == second
    assert cached.stats()["statements"] == 1
    assert TTL_STATEMENTS == 86400
    clock.now += TTL_STATEMENTS + 1
    cached.get_statements("NVDA", years=3)
    assert inner.calls == 2


def test_row_written_by_an_older_schema_is_a_miss(setup, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """A cached Fundamentals row from before `employees` existed must be refetched, not decoded
    with employees=None, which would be indistinguishable from 'Yahoo has no headcount'."""
    import json
    import sqlite3

    inner, cached, _ = setup
    cached.get_fundamentals("AAPL")
    conn = sqlite3.connect(tmp_path / "cache.db")
    with conn:
        (payload,) = conn.execute(
            "SELECT payload FROM entries WHERE kind = 'fundamentals'"
        ).fetchone()
        old = json.loads(payload)
        del old["employees"]  # simulate a row written by 0.2.0
        conn.execute(
            "UPDATE entries SET payload = ? WHERE kind = 'fundamentals'", (json.dumps(old),)
        )
    conn.close()
    assert cached.get_fundamentals("AAPL") == make_fundamentals("AAPL")
    assert inner.calls == 2, "stale-schema row must be refetched"


def test_row_with_unknown_extra_field_is_a_miss(setup, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    import json
    import sqlite3

    inner, cached, _ = setup
    cached.get_quote("AAPL")
    conn = sqlite3.connect(tmp_path / "cache.db")
    with conn:
        (payload,) = conn.execute("SELECT payload FROM entries WHERE kind = 'quote'").fetchone()
        data = json.loads(payload)
        data["renamed_later"] = 1
        conn.execute("UPDATE entries SET payload = ? WHERE kind = 'quote'", (json.dumps(data),))
    conn.close()
    assert cached.get_quote("AAPL").price == 180.0
    assert inner.calls == 2
