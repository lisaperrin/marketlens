import pytest

from marketlens.alerts.engine import Alert, AlertReport, evaluate
from marketlens.alerts.rules import DEFAULT_RULES, AlertRules, Thresholds
from marketlens.data.fake import FakeProvider, make_history, make_quote


def provider() -> FakeProvider:
    rising = [100.0 + i for i in range(40)]  # RSI 100
    calm = [100.0 + (0.3 if i % 2 else -0.3) for i in range(60)]
    spike = [100.0] * 40 + [104.0, 109.0, 115.0]  # above upper band
    return FakeProvider(
        quotes={
            "UP": make_quote("UP", 139.0, 138.0),
            "CALM": make_quote("CALM", 100.3, 99.7),
            "DROP": make_quote("DROP", 94.0, 100.0),  # -6 % day
            "SPIKE": make_quote("SPIKE", 115.0, 109.0),
            "PRICY": make_quote("PRICY", 500.0, 499.0),
        },
        histories={
            "UP": make_history("UP", rising),
            "CALM": make_history("CALM", calm),
            "DROP": make_history("DROP", calm),
            "SPIKE": make_history("SPIKE", spike),
            "PRICY": make_history("PRICY", calm),
        },
    )


def kinds(alerts: list[Alert]) -> set[str]:
    return {a.kind for a in alerts}


def run(symbols: list[str], rules: AlertRules = DEFAULT_RULES) -> list[Alert]:
    report = evaluate(symbols, rules, provider())
    assert isinstance(report, AlertReport)
    return report.alerts


def test_calm_symbol_fires_nothing() -> None:
    report = evaluate(["CALM"], DEFAULT_RULES, provider())
    assert report.alerts == [] and report.errors == [] and report.symbols == ["CALM"]


def test_rsi_above_fires() -> None:
    alerts = run(["UP"])
    assert "rsi_above" in kinds(alerts)
    alert = next(a for a in alerts if a.kind == "rsi_above")
    assert alert.symbol == "UP" and alert.value == pytest.approx(100.0) and alert.threshold == 70.0
    assert "RSI" in alert.message


def test_day_change_abs_fires_on_a_drop() -> None:
    alerts = run(["DROP"])
    assert kinds(alerts) == {"day_change_abs"}
    assert alerts[0].value == pytest.approx(-6.0)


def test_bollinger_breakout_fires_and_can_be_disabled() -> None:
    assert "bollinger_upper" in kinds(run(["SPIKE"]))
    quiet = AlertRules(
        defaults=Thresholds(bollinger=False, day_change_abs=99.0, rsi_above=101.0), per_symbol={}
    )
    assert run(["SPIKE"], quiet) == []


def test_price_thresholds_fire_only_for_their_symbol() -> None:
    rules = AlertRules(defaults=Thresholds(), per_symbol={"PRICY": Thresholds(price_above=400.0)})
    alerts = run(["PRICY", "CALM"], rules)
    assert [(a.symbol, a.kind) for a in alerts] == [("PRICY", "price_above")]
    assert alerts[0].threshold == 400.0 and alerts[0].value == 500.0


def test_rule_symbols_are_added_to_the_watchlist() -> None:
    rules = AlertRules(defaults=Thresholds(), per_symbol={"DROP": Thresholds()})
    report = evaluate(["CALM"], rules, provider())
    assert [a.symbol for a in report.alerts] == ["DROP"]
    assert report.symbols == ["CALM", "DROP"]


def test_alerts_are_json_friendly_and_ordered_by_symbol() -> None:
    report = evaluate(["UP", "DROP"], DEFAULT_RULES, provider())
    assert [a.symbol for a in report.alerts] == sorted(a.symbol for a in report.alerts)
    data = report.alerts[0].to_dict()
    assert set(data) == {"symbol", "kind", "message", "value", "threshold"}
    assert set(report.to_dict()) == {"symbols", "alerts", "errors"}


def test_unknown_symbol_is_reported_and_the_rest_still_evaluated() -> None:
    report = evaluate(["ZZZZ", "DROP", "UP"], DEFAULT_RULES, provider())
    assert {a.symbol for a in report.alerts} == {"DROP", "UP"}
    assert len(report.errors) == 1
    assert report.errors[0]["symbol"] == "ZZZZ" and "ZZZZ" in report.errors[0]["error"]
    assert report.to_dict()["errors"][0]["symbol"] == "ZZZZ"
