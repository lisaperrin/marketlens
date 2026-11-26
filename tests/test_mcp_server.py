import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from marketlens import mcp_server
from marketlens.data.fake import FakeProvider, make_fundamentals, make_history, make_quote

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "portfolio.example.toml"


def fake_provider() -> FakeProvider:
    symbols = {"AAPL": (180.0, 175.0), "MSFT": (400.0, 410.0), "VTI": (250.0, 249.0)}
    closes = {s: [float(100 + i + k) for i in range(60)] for k, s in enumerate(symbols)}
    closes["MSFT"] = [float(300 - i) for i in range(60)]
    return FakeProvider(
        quotes={s: make_quote(s, p, pc) for s, (p, pc) in symbols.items()},
        histories={s: make_history(s, c) for s, c in closes.items()},
        fundamentals={s: make_fundamentals(s) for s in symbols},
    )


@pytest.fixture(autouse=True)
def inject_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = fake_provider()
    monkeypatch.setattr(mcp_server, "provider_factory", lambda: provider)


def call(tool: str, **arguments: Any) -> dict[str, Any]:
    result = asyncio.run(mcp_server.server.call_tool(tool, arguments))
    assert result.structured_content is not None
    assert json.loads(result.content[0].text) == result.structured_content
    return dict(result.structured_content)


def test_server_exposes_the_five_tools() -> None:
    names = {tool.name for tool in asyncio.run(mcp_server.server.list_tools())}
    assert names == {
        "get_quote",
        "analyze_ticker",
        "compare_tickers",
        "portfolio_summary",
        "market_brief",
        "check_alerts",
    }


def test_every_tool_has_a_description() -> None:
    for tool in asyncio.run(mcp_server.server.list_tools()):
        assert tool.description, tool.name


def test_get_quote_returns_price_and_change() -> None:
    data = call("get_quote", symbol="aapl")
    assert data["symbol"] == "AAPL"
    assert data["price"] == 180.0
    assert data["change_pct"] == pytest.approx((180 / 175 - 1) * 100)


def test_analyze_ticker_returns_summary_dict() -> None:
    data = call("analyze_ticker", symbol="AAPL", period="3mo")
    assert data["symbol"] == "AAPL"
    assert data["period"] == "3mo"
    assert data["rsi_14"] == pytest.approx(100.0)
    assert data["fundamentals"]["sector"] == "Technology"


def test_analyze_ticker_rejects_bad_period() -> None:
    with pytest.raises(ToolError, match="period"):
        call("analyze_ticker", symbol="AAPL", period="7y")


def test_compare_tickers_returns_nested_correlation() -> None:
    data = call("compare_tickers", symbols=["AAPL", "MSFT"])
    assert [s["symbol"] for s in data["summaries"]] == ["AAPL", "MSFT"]
    assert data["correlation"]["AAPL"]["AAPL"] == pytest.approx(1.0)
    assert -1.0 <= data["correlation"]["AAPL"]["MSFT"] <= 1.0


def test_compare_tickers_needs_two_symbols() -> None:
    with pytest.raises(ToolError, match="two"):
        call("compare_tickers", symbols=["AAPL"])


def test_portfolio_summary_values_holdings_file() -> None:
    data = call("portfolio_summary", path=str(EXAMPLE))
    assert data["total_value"] == pytest.approx(10 * 180 + 5 * 400 + 20 * 250)
    assert [p["symbol"] for p in data["positions"]] == ["AAPL", "MSFT", "VTI"]


def test_portfolio_summary_missing_file_is_a_tool_error() -> None:
    with pytest.raises(ToolError, match="not found"):
        call("portfolio_summary", path="/definitely/missing.toml")


def test_market_brief_returns_movers() -> None:
    data = call("market_brief", symbols=["AAPL", "MSFT", "VTI"])
    assert data["movers"]["top"]["symbol"] == "AAPL"
    assert data["movers"]["bottom"]["symbol"] == "MSFT"
    assert data["portfolio"] is None


def test_unknown_symbol_is_a_tool_error_naming_the_symbol() -> None:
    with pytest.raises(ToolError, match="ZZZZ"):
        call("get_quote", symbol="ZZZZ")


def test_main_is_an_entry_point() -> None:
    assert callable(mcp_server.main)


def test_period_parameters_are_enums_in_the_tool_schema() -> None:
    tools = {t.name: t for t in asyncio.run(mcp_server.server.list_tools())}
    for name in ("analyze_ticker", "compare_tickers"):
        period = tools[name].input_schema["properties"]["period"]
        assert set(period["enum"]) == {"1mo", "3mo", "6mo", "1y", "2y", "5y", "max"}, name


def test_tools_accept_optional_benchmark() -> None:
    data = call("analyze_ticker", symbol="AAPL", benchmark="VTI")
    assert data["benchmark"]["symbol"] == "VTI"
    data = call("compare_tickers", symbols=["AAPL", "MSFT"], benchmark="VTI")
    assert data["summaries"][0]["benchmark"]["symbol"] == "VTI"
    data = call("portfolio_summary", path=str(EXAMPLE), benchmark="VTI")
    assert data["benchmark"]["symbol"] == "VTI"
    assert call("analyze_ticker", symbol="AAPL")["benchmark"] is None


def test_check_alerts_tool(tmp_path: Path) -> None:
    rules = tmp_path / "alerts.toml"
    rules.write_text('[[rules]]\nsymbol = "AAPL"\nprice_above = 100.0\n')
    data = call("check_alerts", symbols=["MSFT"], rules_path=str(rules))
    assert set(data["symbols"]) == {"AAPL", "MSFT"}
    assert "price_above" in [a["kind"] for a in data["alerts"] if a["symbol"] == "AAPL"]
    names = {tool.name for tool in asyncio.run(mcp_server.server.list_tools())}
    assert "check_alerts" in names
