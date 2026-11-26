# MarketLens 0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in benchmark comparison, EMA/MACD/Bollinger indicators with signals, and an alerts command, as specified in the "v0.2 additions" section of `docs/design.md`.

**Architecture:** Pure functions in `analysis/` extended; `TickerSummary` and `PortfolioValuation` grow optional fields that default to absent; a new `alerts/` package evaluates rules against the provider; CLI, MCP and tables expose the new pieces only when asked.

**Tech Stack:** unchanged (Python 3.12+, pandas, typer, rich, mcp 2.x, pytest).

**Spec:** `docs/design.md`, section "v0.2 additions".

## Global Constraints

- Default output of `analyze`, `compare`, `portfolio` must be byte-identical in structure when no new option is given (existing table tests must not change).
- No test touches the network; `FakeProvider` only.
- Every indicator/statistic gets a hand-computed known-answer test.
- Beta uses daily simple returns aligned with an inner join on dates; fewer than 3 shared returns → `None`.
- Signals look back exactly 5 sessions for crossovers.
- Version bumps to `0.2.0` in `pyproject.toml`, `marketlens.__version__` and `.claude-plugin/plugin.json`.

## Review Focus

1. Benchmark symbol equals the ticker itself → beta 1.0, excess 0.0, no crash. (Task 1)
2. Benchmark history shorter than the ticker's → stats computed over the overlap only. (Task 1)
3. Bollinger on a constant series → bands equal the price, no NaN division warnings; signals empty. (Task 3)
4. `alerts.toml` rule for a symbol not in the watchlist → still evaluated (rules add symbols). (Task 4)
5. `--fail-on-alert` with no alerts → exit 0; with alerts → exit 3 and output still printed. (Task 4)

---

### Task 1: Benchmark statistics and ticker-level comparison

**Files:** Modify `src/marketlens/analysis/stats.py`, `src/marketlens/analysis/summary.py`; tests `tests/analysis/test_stats.py`, `tests/analysis/test_summary.py`.

**Interfaces — Produces:** `stats.beta(close, benchmark_close) -> float | None`; `stats.aligned_total_returns(close, benchmark_close) -> tuple[float, float]` (both over the shared date range); `summary.BenchmarkComparison(symbol, period, benchmark_return, excess_return, beta)` with `to_dict()`; `summarize(symbol, provider, period="1y", benchmark: str | None = None)` setting `TickerSummary.benchmark: BenchmarkComparison | None` (default `None`, included in `to_dict`); `compare(symbols, provider, period, benchmark=None)`.

- [ ] Tests: `beta` of a series against itself == 1.0; of `2x` daily moves == 2.0 (construct closes so returns are exactly doubled: use returns r and 2r); constant benchmark → `None`; overlap shorter than 3 → `None`; `aligned_total_returns` restricts to overlap; `summarize(..., benchmark="SPY")` populates `benchmark` with `excess_return == total_return - benchmark_return`; `to_dict()["benchmark"]` is `None` without a benchmark.
- [ ] RED → implement → GREEN → commit `feat(analysis): benchmark beta and excess return`.

### Task 2: Benchmark in portfolio, CLI, tables and MCP

**Files:** Modify `src/marketlens/portfolio/holdings.py` (`Portfolio.benchmark: str | None`, TOML key `benchmark`), `valuation.py` (`PortfolioBenchmark(symbol, period, day_change_pct, weighted_beta)`; `value_portfolio(portfolio, provider, benchmark=None, period="1y")` uses the argument, else `portfolio.benchmark`), `cli.py` (`--benchmark/-b` on analyze, compare, portfolio), `report/tables.py` (rows/columns/line only when present), `mcp_server.py` (optional `benchmark`); tests in the matching files.

- [ ] Tests: TOML `benchmark = "vwce.de"` → upper-cased; CLI `--json analyze AAPL -b SPY` has `benchmark.beta`; `portfolio --json` with TOML benchmark has `benchmark.weighted_beta`; without any benchmark `benchmark` is `None` and the rendered table text is unchanged versus today (no "Benchmark" substring); MCP `analyze_ticker(symbol, benchmark=...)`.
- [ ] RED → implement → GREEN → commit `feat: opt-in benchmark on analyze, compare and portfolio`.

### Task 3: EMA, MACD, Bollinger Bands and signals

**Files:** Modify `src/marketlens/analysis/indicators.py`, `summary.py` (`IndicatorSnapshot`, `signals`), `report/tables.py` (`indicator_table`, "Signals" row), `cli.py` (`analyze --indicators`); tests `tests/analysis/test_indicators.py`, `test_summary.py`, `tests/test_tables.py`, `tests/test_cli.py`.

**Interfaces — Produces:** `ema(close, span) -> Series` (pandas `ewm(span, adjust=False)`, NaN before `span` observations); `macd(close, fast=12, slow=26, signal=9) -> DataFrame` columns `macd, signal, histogram`; `bollinger(close, window=20, num_std=2.0) -> DataFrame` columns `middle, upper, lower` (sample std); `IndicatorSnapshot(ema_20, macd, macd_signal, macd_histogram, bb_upper, bb_middle, bb_lower)` all `float | None`; `signals(close, summary_inputs) -> tuple[str, ...]`; `TickerSummary.indicators`, `TickerSummary.signals`.

- [ ] Known-answer tests: `ema([1,2,3,4,5], span=3)` last value hand-computed with alpha 0.5 (seeded by the first value): 1→1.5→2.25→3.125→4.0625; `macd` of a constant series is all zeros after warm-up; `bollinger([1..5], window=5)` middle 3, std sqrt(2.5), upper 3+2·1.5811; constant series bands == price; signals: price above upper band produces one sentence containing "upper Bollinger"; RSI 100 series produces "overbought"; no signals for a short flat series.
- [ ] CLI: `--json analyze` includes `indicators` and `signals`; `analyze --indicators` output contains "MACD"; default `analyze` output does not.
- [ ] RED → implement → GREEN → commit `feat(analysis): EMA, MACD, Bollinger Bands and signals`.

### Task 4: Alerts

**Files:** Create `src/marketlens/alerts/__init__.py`, `rules.py`, `engine.py`, `examples/alerts.example.toml`; modify `cli.py`, `mcp_server.py`, `report/tables.py` (`alerts_table`); tests `tests/alerts/test_rules.py`, `test_engine.py`, `tests/test_cli.py`, `tests/test_mcp_server.py`.

**Interfaces — Produces:** `Thresholds(rsi_above=70.0, rsi_below=30.0, day_change_abs=5.0, price_above=None, price_below=None, bollinger=True)`; `AlertRules(defaults: Thresholds, per_symbol: dict[str, Thresholds])` with `for_symbol(symbol)`; `load_rules(path) -> AlertRules` (missing keys fall back to defaults; `HoldingsFileError` reused for bad files); `Alert(symbol, kind, message, value, threshold)` with `to_dict()`; `evaluate(symbols, rules, provider, period="6mo") -> list[Alert]`; CLI `alerts` with `--watchlist`, `--portfolio`, `--rules`, `--fail-on-alert`; MCP `check_alerts(symbols, rules_path=None, portfolio_path=None)`.

- [ ] Tests: default thresholds; per-symbol override merges with defaults; rule symbols are added to the evaluated set; RSI-100 series fires `rsi_above`; day change −6 % fires `day_change_abs`; price 500 with `price_above = 400` fires; nothing fires on a calm series; CLI prints "No alerts" and exits 0; `--fail-on-alert` exits 3 when something fired; `--json` returns a list.
- [ ] RED → implement → GREEN → commit `feat(alerts): threshold alerts command and MCP tool`.

### Task 5: Docs, skills, version, verification

- [ ] `skills/check-alerts/SKILL.md`; mention benchmark in `analyze-ticker`, `compare-tickers`, `portfolio-review`; mention alerts in `market-brief`; update `tests/test_plugin_config.py` expected skills; `agents/market-analyst.md` tool list gains `check_alerts`.
- [ ] README: new sections for benchmark, indicators, alerts; `examples/alerts.example.toml`.
- [ ] Version 0.2.0 in three places; `uv lock`.
- [ ] Full gate on 3.12 and isolated 3.13; `validate_plugin.py --with-claude-cli`; live smoke of `analyze NVD.DE -b VWCE.DE --indicators`, `portfolio -b VWCE.DE`, `alerts --portfolio portfolio.toml`.
- [ ] Commit `feat: release 0.2.0`, push, fresh whole-branch review, fix pass, push.
