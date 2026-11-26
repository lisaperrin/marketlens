"""A SQLite-backed caching decorator for any :class:`MarketDataProvider`."""

from __future__ import annotations

import dataclasses
import json
import os
import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from marketlens.data.models import Fundamentals, Interval, Period, Quote, validate_history
from marketlens.data.provider import MarketDataProvider

TTL_QUOTE = 900
"""Seconds a quote stays fresh (15 minutes)."""
TTL_HISTORY = 3600
"""Seconds a price history stays fresh (1 hour)."""
TTL_FUNDAMENTALS = 86400
"""Seconds fundamentals stay fresh (24 hours)."""

KINDS: tuple[str, ...] = ("quote", "history", "fundamentals")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    kind       TEXT NOT NULL,
    key        TEXT NOT NULL,
    fetched_at REAL NOT NULL,
    payload    TEXT NOT NULL,
    PRIMARY KEY (kind, key)
)
"""


def default_cache_path() -> Path:
    """Return ``$XDG_CACHE_HOME/marketlens/cache.db`` (default ``~/.cache``)."""
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "marketlens" / "cache.db"


class CachedProvider:
    """Wrap a provider and memoise its answers in SQLite with per-kind TTLs.

    Errors from the inner provider are never cached. A row whose payload cannot be
    decoded is treated as a miss and overwritten.
    """

    def __init__(
        self,
        inner: MarketDataProvider,
        path: Path | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._inner = inner
        self._path = path or default_cache_path()
        self._clock = clock
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create the table; if the file is not a usable database, move it aside and start over."""
        try:
            with self._connect() as conn:
                conn.execute(_SCHEMA)
        except sqlite3.DatabaseError:
            self._quarantine()
            with self._connect() as conn:
                conn.execute(_SCHEMA)

    def _quarantine(self) -> None:
        """Rename an unreadable cache file so it is kept for inspection but no longer used."""
        if self._path.exists():
            stamp = time.strftime("%Y%m%d-%H%M%S")
            self._path.rename(self._path.with_name(f"{self._path.name}.corrupt-{stamp}"))

    # -- MarketDataProvider -------------------------------------------------------------

    def get_quote(self, symbol: str) -> Quote:
        """Return a cached quote when fresh, otherwise fetch and store."""
        symbol = symbol.upper()
        quote: Quote = self._through(
            "quote",
            symbol,
            TTL_QUOTE,
            fetch=lambda: self._inner.get_quote(symbol),
            encode=_encode_dataclass,
            decode=_decode_quote,
        )
        return quote

    def get_history(
        self, symbol: str, period: Period = "1y", interval: Interval = "1d"
    ) -> pd.DataFrame:
        """Return cached history when fresh, otherwise fetch and store."""
        symbol = symbol.upper()
        return self._through(
            "history",
            f"{symbol}:{period}:{interval}",
            TTL_HISTORY,
            fetch=lambda: self._inner.get_history(symbol, period, interval),
            encode=_encode_history,
            decode=_decode_history,
        )

    def get_fundamentals(self, symbol: str) -> Fundamentals:
        """Return cached fundamentals when fresh, otherwise fetch and store."""
        symbol = symbol.upper()
        fundamentals: Fundamentals = self._through(
            "fundamentals",
            symbol,
            TTL_FUNDAMENTALS,
            fetch=lambda: self._inner.get_fundamentals(symbol),
            encode=_encode_dataclass,
            decode=lambda raw: Fundamentals(**json.loads(raw)),
        )
        return fundamentals

    # -- maintenance --------------------------------------------------------------------

    def clear(self) -> int:
        """Delete every cached row and return how many were removed.

        An unreadable cache file counts as one removed entry: it is moved aside and recreated.
        """
        try:
            with self._connect() as conn:
                return int(conn.execute("DELETE FROM entries").rowcount)
        except sqlite3.DatabaseError:
            self._quarantine()
            self._ensure_schema()
            return 1

    def stats(self) -> dict[str, int]:
        """Return the number of rows stored per kind (all zero if the file is unreadable)."""
        counts = dict.fromkeys(KINDS, 0)
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT kind, COUNT(*) FROM entries GROUP BY kind").fetchall()
        except sqlite3.DatabaseError:
            return counts
        for kind, count in rows:
            counts[str(kind)] = int(count)
        return counts

    @property
    def path(self) -> Path:
        """Location of the SQLite file."""
        return self._path

    # -- internals ----------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a connection that commits on success, rolls back on error and always closes."""
        conn = sqlite3.connect(self._path, timeout=10.0)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _through[T](
        self,
        kind: str,
        key: str,
        ttl: int,
        *,
        fetch: Callable[[], T],
        encode: Callable[[T], str],
        decode: Callable[[str], T],
    ) -> T:
        now = self._clock()
        row = self._read(kind, key)
        if row is not None and now - float(row[0]) < ttl:
            try:
                return decode(str(row[1]))
            except Exception:
                pass
        value = fetch()
        self._write(kind, key, now, encode(value))
        return value

    def _read(self, kind: str, key: str) -> tuple[float, str] | None:
        """Fetch a row; an unreadable database is a miss, and the file is recreated."""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT fetched_at, payload FROM entries WHERE kind = ? AND key = ?",
                    (kind, key),
                ).fetchone()
        except sqlite3.DatabaseError:
            self._quarantine()
            self._ensure_schema()
            return None
        return None if row is None else (float(row[0]), str(row[1]))

    def _write(self, kind: str, key: str, fetched_at: float, payload: str) -> None:
        """Store a row; failing to cache is never a reason to fail the request."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO entries (kind, key, fetched_at, payload) "
                    "VALUES (?, ?, ?, ?)",
                    (kind, key, fetched_at, payload),
                )
        except sqlite3.DatabaseError:
            return


def _encode_dataclass(value: Any) -> str:
    return json.dumps(dataclasses.asdict(value), default=_json_default)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Cannot serialise {type(value).__name__}")


def _decode_quote(raw: str) -> Quote:
    data = json.loads(raw)
    data["as_of"] = datetime.fromisoformat(data["as_of"])
    return Quote(**data)


def _encode_history(frame: pd.DataFrame) -> str:
    return str(frame.to_json(orient="split", date_format="iso", date_unit="ns"))


def _decode_history(raw: str) -> pd.DataFrame:
    frame = pd.read_json(StringIO(raw), orient="split")
    frame.index = pd.to_datetime(frame.index)
    frame.index.name = "Date"
    return validate_history(frame)
