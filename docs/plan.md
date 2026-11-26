# MarketLens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MarketLens Python toolkit (library, CLI, MCP server) and its Claude Code plugin as described in `docs/design.md`.

**Architecture:** A `MarketDataProvider` Protocol with a yfinance implementation and a SQLite cache feeds pure pandas analysis functions, a portfolio valuation module, a Typer CLI and a FastMCP server. The repo root is also a Claude Code plugin (skills, agents, hooks, `.mcp.json`).

**Tech Stack:** Python 3.12+, uv, yfinance, pandas, typer, rich, mcp (FastMCP), pytest, ruff, mypy, GitHub Actions.

**Spec:** `docs/design.md`

## Global Constraints

- Python `>=3.12`; every command runs through `uv run`; `uv.lock` committed.
- Runtime deps limited to `yfinance pandas typer rich mcp`; dev deps `pytest pytest-cov ruff mypy pandas-stubs`.
- No test may open a network connection. All data comes from `FakeProvider`.
- Ruff line length 100; `ruff check` and `ruff format --check` and `mypy src` clean.
- Commit after every task with conventional-commit messages.
- Cache TTLs exactly: quote 900 s, history 3600 s, fundamentals 86400 s.
- Hook scripts are POSIX `sh`, exit 0 on success, exit 2 to block, and read the hook JSON from stdin.

## Review Focus

1. Ticker with no data (delisted or typo): `get_history` returns an empty frame → must raise `SymbolNotFoundError`, not return NaN stats. (Task 2 test.)
2. Close series shorter than the indicator window (e.g. 5 rows, SMA 20) → functions return a Series of NaN / `None` rather than raising. (Task 3 test.)
3. Holdings file with a zero or negative `shares` value → `HoldingsFileError` with the offending symbol in the message. (Task 4 test.)
4. Cache entry from a previous schema or corrupted JSON → treated as a miss and refetched, never a crash. (Task 2 test.)
5. Hook receives tool input without `file_path` (e.g. a `Write` to a notebook) → exits 0 silently. (Task 7 test.)

---

### Task 1: Project scaffold

**Files:** Create `pyproject.toml`, `README.md`, `LICENSE`, `.gitignore`, `.python-version`, `src/marketlens/__init__.py`, `src/marketlens/errors.py`, `tests/__init__.py`, `tests/test_errors.py`, `.github/workflows/ci.yml`.

**Interfaces — Produces:** `marketlens.errors.MarketLensError`, `SymbolNotFoundError(symbol)`, `DataUnavailableError`, `HoldingsFileError`; `marketlens.__version__ = "0.1.0"`.

- [ ] Write `tests/test_errors.py`: `SymbolNotFoundError("ZZZZ")` is a `MarketLensError`, its `str` contains `ZZZZ`, and `.symbol == "ZZZZ"`.
- [ ] `uv run pytest` → FAIL (module missing).
- [ ] Create `pyproject.toml` (build backend `uv_build`, scripts `marketlens = "marketlens.cli:app"` and `marketlens-mcp = "marketlens.mcp_server:main"`, ruff `line-length = 100`, `select = ["E","F","I","B","UP","N","SIM","RUF"]`, mypy `strict = true` for `src`, pytest `testpaths = ["tests"]`), `uv sync`, implement errors.
- [ ] `uv run pytest` → PASS; `uv run ruff check . && uv run ruff format --check . && uv run mypy src` → clean.
- [ ] Add `ci.yml` (astral-sh/setup-uv, `uv sync --locked`, lint, type-check, test on 3.12 and 3.13). Commit `chore: scaffold project`.

### Task 2: Data layer

**Files:** Create `src/marketlens/data/__init__.py`, `models.py`, `provider.py`, `fake.py`, `yfinance_provider.py`, `cache.py`; tests `tests/data/test_models.py`, `test_fake.py`, `test_cache.py`, `test_yfinance_provider.py`.

**Interfaces — Produces:**
- `Quote(symbol: str, name: str, price: float, previous_close: float, currency: str, as_of: datetime)` with property `change_pct -> float`.
- `Fundamentals(symbol, market_cap: int|None, trailing_pe: float|None, forward_pe: float|None, dividend_yield: float|None, beta: float|None, sector: str|None, industry: str|None, fifty_two_week_high: float|None, fifty_two_week_low: float|None)`.
- `Period = Literal["1mo","3mo","6mo","1y","2y","5y","max"]`, `Interval = Literal["1d","1wk","1mo"]`.
- `class MarketDataProvider(Protocol)`: `get_quote(symbol) -> Quote`, `get_history(symbol, period="1y", interval="1d") -> pd.DataFrame`, `get_fundamentals(symbol) -> Fundamentals`.
- `validate_history(df) -> pd.DataFrame` enforces DatetimeIndex + OHLCV columns, raises `DataUnavailableError`.
- `FakeProvider(quotes: dict[str, Quote], histories: dict[str, pd.DataFrame], fundamentals: dict[str, Fundamentals])` raising `SymbolNotFoundError` for unknown symbols; helper `make_history(symbol, closes: list[float], start="2024-01-01") -> pd.DataFrame`.
- `YFinanceProvider()` wrapping `yf.Ticker`; empty history → `SymbolNotFoundError`.
- `CachedProvider(inner, path: Path | None = None, clock=time.time)` with `clear() -> int` (rows deleted) and `stats() -> dict[str, int]`; TTLs per Global Constraints.

- [ ] Tests: `Quote.change_pct` for 110 vs 100 == 10.0; `validate_history` rejects missing `Close`; `FakeProvider` unknown symbol raises; cache hit returns inner result without second inner call (count calls); cache expires after TTL using injected clock; corrupted payload row → refetch; `clear()` returns row count.
- [ ] `uv run pytest tests/data` → FAIL.
- [ ] Implement models, protocol, fake, cache (sqlite3 stdlib, table `entries(kind, key, fetched_at REAL, payload TEXT)`, history serialised with `to_json(orient="split", date_format="iso")`, quote/fundamentals via `dataclasses.asdict` + `json`).
- [ ] Implement `YFinanceProvider`; test it with `yf.Ticker` monkeypatched to a stub object exposing `.fast_info`, `.history()`, `.info` so no network.
- [ ] `uv run pytest tests/data` → PASS. Commit `feat(data): provider protocol, yfinance provider, sqlite cache`.

### Task 3: Analysis

**Files:** Create `src/marketlens/analysis/__init__.py`, `indicators.py`, `stats.py`, `summary.py`; tests `tests/analysis/test_indicators.py`, `test_stats.py`, `test_summary.py`.

**Interfaces — Produces:** (all take `close: pd.Series`)
- `indicators.sma(close, window) -> pd.Series`, `indicators.rsi(close, window=14) -> pd.Series` (Wilder smoothing).
- `stats.daily_returns(close) -> pd.Series`, `total_return(close) -> float`, `annualized_volatility(close, periods_per_year=252) -> float`, `max_drawdown(close) -> float` (negative fraction), `sharpe_ratio(close, risk_free=0.0, periods_per_year=252) -> float`, `correlation_matrix(closes: dict[str, pd.Series]) -> pd.DataFrame`.
- `summary.TickerSummary` frozen dataclass: `quote, fundamentals, period, total_return, annualized_volatility, max_drawdown, sharpe_ratio, sma_50, sma_200, rsi_14, last_close` with `to_dict() -> dict[str, Any]`.
- `summary.summarize(symbol, provider, period="1y") -> TickerSummary`.
- `summary.compare(symbols, provider, period="1y") -> Comparison(summaries: list[TickerSummary], correlation: pd.DataFrame)` with `to_dict()`.

- [ ] Known-answer tests: `sma([1..5], 3)` last value 4.0; `total_return([100,110])` == 0.10; `max_drawdown([100,120,90,100])` == -0.25; constant series volatility 0.0; RSI of strictly rising series == 100.0; short series (5 rows) `sma(window=20)` all NaN, `summarize` yields `sma_200 is None`.
- [ ] FAIL → implement → PASS. Commit `feat(analysis): indicators, risk stats, ticker summary`.

### Task 4: Portfolio

**Files:** Create `src/marketlens/portfolio/__init__.py`, `holdings.py`, `valuation.py`, `examples/portfolio.example.toml`; tests `tests/portfolio/test_holdings.py`, `test_valuation.py`.

**Interfaces — Produces:**
- `Holding(symbol: str, shares: float, cost_basis: float)`; `Portfolio(base_currency: str, holdings: tuple[Holding, ...])`; `load_portfolio(path: Path) -> Portfolio` (tomllib) raising `HoldingsFileError`.
- `Position(symbol, shares, cost_basis, price, market_value, cost, pnl, pnl_pct, day_change_pct, weight)`.
- `PortfolioValuation(base_currency, positions: tuple[Position, ...], total_value, total_cost, total_pnl, total_pnl_pct)` with `to_dict()`.
- `value_portfolio(portfolio, provider) -> PortfolioValuation`.

- [ ] Tests: load example file; missing `symbol` key → `HoldingsFileError`; `shares <= 0` → `HoldingsFileError` naming the symbol; valuation of 10 AAPL @150 cost, price 180 → `market_value 1800`, `pnl 300`, `pnl_pct 0.20`; weights sum to 1.0 within 1e-9.
- [ ] FAIL → implement → PASS. Commit `feat(portfolio): holdings loader and valuation`.

### Task 5: Report rendering and CLI

**Files:** Create `src/marketlens/report/__init__.py`, `tables.py`, `src/marketlens/cli.py`; tests `tests/test_cli.py` (Typer `CliRunner`, provider injected via `marketlens.cli.get_provider` monkeypatch).

**Interfaces — Produces:** `tables.quote_table(quotes) -> rich.table.Table`, `summary_table(summary)`, `comparison_table(comparison)`, `portfolio_table(valuation)`; CLI commands `quote SYMBOLS...`, `analyze SYMBOL [--period]`, `compare SYMBOLS... [--period]`, `portfolio [PATH]` (default `portfolio.toml`), `brief [--watchlist a,b] [--portfolio PATH]`, `cache stats|clear`; global options `--json`, `--no-cache`; `get_provider(no_cache: bool) -> MarketDataProvider`.

- [ ] Tests: `quote AAPL --json` prints JSON with `price`; `analyze ZZZZ` exits 1 with `ZZZZ` in output; `portfolio examples/portfolio.example.toml --json` includes `total_value`; `--help` lists all commands.
- [ ] FAIL → implement → PASS. Commit `feat(cli): typer commands and rich tables`.

### Task 6: MCP server

**Files:** Create `src/marketlens/mcp_server.py`; tests `tests/test_mcp_server.py` (call the underlying tool functions directly with an injected provider).

**Interfaces — Produces:** FastMCP server `marketlens` with tools `get_quote(symbol)`, `analyze_ticker(symbol, period="1y")`, `compare_tickers(symbols: list[str], period="1y")`, `portfolio_summary(path: str)`, `market_brief(symbols: list[str])`, all returning `dict`; `main()` runs stdio transport; module-level `provider_factory` for tests.

- [ ] Tests: `get_quote` dict has `symbol`, `price`, `change_pct`; unknown symbol raises `SymbolNotFoundError` (FastMCP converts to tool error); `compare_tickers` returns `correlation` matrix as nested dict.
- [ ] FAIL → implement → PASS. Commit `feat(mcp): stdio server exposing market tools`.

### Task 7: Claude Code plugin and project configuration

**Files:** Create `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.mcp.json`, `hooks/hooks.json`, `hooks/scripts/session-start.sh`, `hooks/scripts/ticker-hint.sh`, `skills/{analyze-ticker,compare-tickers,portfolio-review,market-brief,add-indicator}/SKILL.md`, `agents/{market-analyst,quant-reviewer}.md`, `.claude/settings.json`, `.claude/hooks/format-python.sh`, `.claude/hooks/guard-git.sh`, `CLAUDE.md`, `scripts/validate_plugin.py`; tests `tests/test_plugin_config.py`, `tests/test_hooks.py` (run scripts with `subprocess`, feed JSON on stdin).

- [ ] Tests: every JSON file parses; `plugin.json.name == marketplace plugins[0].name == "marketlens"`; each `skills/*/SKILL.md` has frontmatter with `name` and `description`; `format-python.sh` with `{"tool_input":{"file_path":"x.py"}}` on a temp unformatted file reformats it and exits 0; with no `file_path` exits 0; `guard-git.sh` exits 2 for `git push --force origin main` and 0 for `git status`; `ticker-hint.sh` prints `additionalContext` JSON when prompt contains `$AAPL`.
- [ ] FAIL → write files → PASS; `uv run python scripts/validate_plugin.py` prints `OK`. Commit `feat(plugin): skills, agents, hooks, mcp config`.

### Task 8: Documentation, verification and publish

- [ ] README: badges, what it does, 60-second quickstart (`uv sync`, `uv run marketlens quote AAPL`), plugin install (`claude plugin marketplace add lisaperrin/marketlens`), architecture diagram, development section, hook/skill/agent table.
- [ ] Full gate: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- [ ] Live smoke (network, not a test): `uv run marketlens analyze AAPL`, `uv run marketlens-mcp` handshake via a 5-line stdio client.
- [ ] Create private repo via `gh api user/repos -f name=marketlens -F private=true`, push `main`. Commit `docs: readme and quickstart`.
