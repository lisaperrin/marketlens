"""Alert thresholds and the TOML file that configures them.

Format::

    [defaults]                 # optional; missing keys keep the built-in defaults
    rsi_above = 70
    rsi_below = 30
    day_change_abs = 5.0       # percent
    bollinger = true

    [[rules]]                  # optional; per-symbol overrides, merged over the defaults
    symbol = "NVDA"
    price_below = 120.0
    price_above = 200.0
"""

from __future__ import annotations

import dataclasses
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from marketlens.errors import HoldingsFileError

_NUMERIC = ("rsi_above", "rsi_below", "day_change_abs", "price_above", "price_below")


@dataclass(frozen=True, slots=True)
class Thresholds:
    """What counts as notable for one symbol. ``None`` disables a price threshold."""

    rsi_above: float = 70.0
    rsi_below: float = 30.0
    day_change_abs: float = 5.0
    """Absolute day change, in percent, at or above which an alert fires."""
    price_above: float | None = None
    price_below: float | None = None
    bollinger: bool = True
    """Fire when the close is outside the 20-day, 2-std Bollinger Bands."""

    def merged(self, overrides: dict[str, Any]) -> Thresholds:
        """Return a copy with ``overrides`` applied on top."""
        return dataclasses.replace(self, **overrides)


@dataclass(frozen=True, slots=True)
class AlertRules:
    """Default thresholds plus per-symbol overrides."""

    defaults: Thresholds
    per_symbol: dict[str, Thresholds]

    def for_symbol(self, symbol: str) -> Thresholds:
        """Thresholds that apply to ``symbol`` (case-insensitive)."""
        return self.per_symbol.get(symbol.upper(), self.defaults)

    @property
    def symbols(self) -> tuple[str, ...]:
        """Symbols with their own rules; they are always evaluated."""
        return tuple(self.per_symbol)


DEFAULT_RULES = AlertRules(defaults=Thresholds(), per_symbol={})


def load_rules(path: Path) -> AlertRules:
    """Parse an alert rules file.

    Raises:
        HoldingsFileError: if the file is missing, invalid TOML, or has bad values.
    """
    if not path.is_file():
        raise HoldingsFileError(f"Alert rules file not found: {path}")
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise HoldingsFileError(f"{path} is not valid TOML: {exc}") from exc

    defaults = Thresholds().merged(_overrides(document.get("defaults", {}), "defaults"))
    per_symbol: dict[str, Thresholds] = {}
    for index, entry in enumerate(document.get("rules", []), start=1):
        if not isinstance(entry, dict):
            raise HoldingsFileError(f"rules[{index}] must be a table")
        symbol = entry.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise HoldingsFileError(f"rules[{index}] is missing a 'symbol'")
        symbol = symbol.strip().upper()
        per_symbol[symbol] = defaults.merged(_overrides(entry, symbol))
    return AlertRules(defaults=defaults, per_symbol=per_symbol)


def _overrides(table: Any, where: str) -> dict[str, Any]:
    if not isinstance(table, dict):
        raise HoldingsFileError(f"{where} must be a table")
    result: dict[str, Any] = {}
    for key, value in table.items():
        if key == "symbol":
            continue
        if key in _NUMERIC:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise HoldingsFileError(f"{where}: '{key}' must be a number")
            result[key] = float(value)
        elif key == "bollinger":
            if not isinstance(value, bool):
                raise HoldingsFileError(f"{where}: 'bollinger' must be true or false")
            result[key] = value
        else:
            raise HoldingsFileError(f"{where}: unknown key '{key}'")
    return result
