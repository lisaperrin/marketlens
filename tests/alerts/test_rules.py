from pathlib import Path

import pytest

from marketlens.alerts.rules import DEFAULT_RULES, AlertRules, Thresholds, load_rules
from marketlens.errors import HoldingsFileError

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "alerts.example.toml"


def test_default_thresholds() -> None:
    t = Thresholds()
    assert (t.rsi_above, t.rsi_below, t.day_change_abs) == (70.0, 30.0, 5.0)
    assert t.price_above is None and t.price_below is None and t.bollinger is True
    assert DEFAULT_RULES.for_symbol("ANY") == Thresholds()


def test_example_file_loads_and_merges_per_symbol_overrides() -> None:
    rules = load_rules(EXAMPLE)
    assert isinstance(rules, AlertRules)
    nvda = rules.for_symbol("nvda")
    assert nvda.price_below == 120.0 and nvda.price_above == 200.0
    assert nvda.rsi_above == 70.0  # inherited from defaults
    vti = rules.for_symbol("VTI")
    assert vti.day_change_abs == 2.0 and vti.bollinger is False
    assert rules.symbols == ("NVDA", "VTI")


def test_defaults_section_overrides_built_in_defaults(tmp_path: Path) -> None:
    path = tmp_path / "alerts.toml"
    path.write_text("[defaults]\nrsi_above = 80\n")
    assert load_rules(path).for_symbol("AAPL").rsi_above == 80.0
    assert load_rules(path).for_symbol("AAPL").rsi_below == 30.0


def test_missing_file_and_bad_values_raise(tmp_path: Path) -> None:
    with pytest.raises(HoldingsFileError, match="not found"):
        load_rules(tmp_path / "nope.toml")
    bad = tmp_path / "bad.toml"
    bad.write_text('[[rules]]\nsymbol = "AAPL"\nrsi_above = "high"\n')
    with pytest.raises(HoldingsFileError, match="rsi_above"):
        load_rules(bad)
    no_symbol = tmp_path / "nosym.toml"
    no_symbol.write_text("[[rules]]\nprice_above = 1\n")
    with pytest.raises(HoldingsFileError, match="symbol"):
        load_rules(no_symbol)
