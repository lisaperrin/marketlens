import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from marketlens import cli
from marketlens.data.cache import CachedProvider
from marketlens.data.fake import FakeProvider, make_fundamentals, make_history, make_quote

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "portfolio.example.toml"
runner = CliRunner()


def fake_provider() -> FakeProvider:
    symbols = {"AAPL": (180.0, 175.0), "MSFT": (400.0, 410.0), "VTI": (250.0, 249.0)}
    closes = {
        "AAPL": [float(150 + i * 0.5) for i in range(260)],
        "MSFT": [float(300 + (i % 7)) for i in range(260)],
        "VTI": [float(200 + i * 0.2) for i in range(260)],
    }
    return FakeProvider(
        quotes={s: make_quote(s, p, pc) for s, (p, pc) in symbols.items()},
        histories={s: make_history(s, c) for s, c in closes.items()},
        fundamentals={s: make_fundamentals(s) for s in symbols},
    )


@pytest.fixture(autouse=True)
def inject_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    provider = fake_provider()
    cached = CachedProvider(provider, path=tmp_path / "cache.db")
    monkeypatch.setattr(cli, "get_provider", lambda no_cache=False: provider)
    monkeypatch.setattr(cli, "get_cache", lambda: cached)


def test_help_lists_every_command() -> None:
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    for command in ("quote", "analyze", "compare", "portfolio", "brief", "cache"):
        assert command in result.output


def test_quote_prints_table_with_price() -> None:
    result = runner.invoke(cli.app, ["quote", "AAPL", "MSFT"])
    assert result.exit_code == 0
    assert "AAPL" in result.output
    assert "180.00" in result.output


def test_quote_json_output() -> None:
    result = runner.invoke(cli.app, ["--json", "quote", "AAPL"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["symbol"] == "AAPL"
    assert data[0]["price"] == 180.0
    assert data[0]["change_pct"] == pytest.approx((180 / 175 - 1) * 100)


def test_analyze_json_includes_stats() -> None:
    result = runner.invoke(cli.app, ["--json", "analyze", "AAPL", "--period", "6mo"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["symbol"] == "AAPL"
    assert data["period"] == "6mo"
    assert "total_return" in data and "rsi_14" in data


def test_analyze_rejects_bad_period() -> None:
    result = runner.invoke(cli.app, ["analyze", "AAPL", "--period", "7y"])
    assert result.exit_code != 0


def test_unknown_symbol_exits_one_with_message() -> None:
    result = runner.invoke(cli.app, ["analyze", "ZZZZ"])
    assert result.exit_code == 1
    assert "ZZZZ" in result.output


def test_compare_json_has_correlation() -> None:
    result = runner.invoke(cli.app, ["--json", "compare", "AAPL", "MSFT"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert [s["symbol"] for s in data["summaries"]] == ["AAPL", "MSFT"]
    assert "MSFT" in data["correlation"]["AAPL"]


def test_compare_needs_two_symbols() -> None:
    result = runner.invoke(cli.app, ["compare", "AAPL"])
    assert result.exit_code != 0
    assert "two" in result.output.lower()


def test_portfolio_json_has_totals() -> None:
    result = runner.invoke(cli.app, ["--json", "portfolio", str(EXAMPLE)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_value"] == pytest.approx(10 * 180 + 5 * 400 + 20 * 250)


def test_portfolio_missing_file_exits_one() -> None:
    result = runner.invoke(cli.app, ["portfolio", "does-not-exist.toml"])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_brief_json_combines_watchlist_and_portfolio() -> None:
    args = ["--json", "brief", "--watchlist", "AAPL,MSFT", "--portfolio", str(EXAMPLE)]
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert [q["symbol"] for q in data["watchlist"]] == ["AAPL", "MSFT"]
    assert data["portfolio"]["total_value"] > 0
    assert data["movers"]["top"]["symbol"] == "AAPL"
    assert data["movers"]["bottom"]["symbol"] == "MSFT"


def test_brief_without_inputs_fails_clearly() -> None:
    result = runner.invoke(cli.app, ["brief"])
    assert result.exit_code != 0
    assert "watchlist" in result.output.lower()


def test_cache_stats_and_clear() -> None:
    cache = cli.get_cache()
    cache.get_quote("AAPL")
    result = runner.invoke(cli.app, ["--json", "cache", "stats"])
    assert result.exit_code == 0
    assert json.loads(result.output)["quote"] == 1
    result = runner.invoke(cli.app, ["cache", "clear"])
    assert result.exit_code == 0
    assert "1" in result.output
    assert cache.stats()["quote"] == 0
