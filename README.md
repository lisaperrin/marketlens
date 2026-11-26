# marketlens

CLI and MCP server for stock research on top of [yfinance](https://github.com/ranaroussi/yfinance).
Also a Claude Code plugin.

[![CI](https://github.com/lisaperrin/marketlens/actions/workflows/ci.yml/badge.svg)](https://github.com/lisaperrin/marketlens/actions/workflows/ci.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

```text
╭──────────────────── AAPL · Apple Inc. ────────────────────╮
│ Price                                          355.58 USD │
│ Day change                                         +0.63% │
│ Total return (6mo)                                +15.51% │
│ Annualised volatility                              27.43% │
│ Max drawdown                                      -12.71% │
│ Sharpe ratio                                         1.17 │
│ SMA 50 / 200                                   342.84 / — │
│ RSI 14                                               58.0 │
│ Market cap                                          5.17T │
│ P/E trailing / forward                      39.60 / 33.63 │
│ 52-week range                             243.42 / 360.83 │
│ Sector / industry       Technology / Consumer Electronics │
│ Data as of                 2026-11-26 17:16 CET (delayed) │
╰───────────────────────────────────────────────────────────╯
```

Quick reads on single stocks, side-by-side comparisons, portfolio valuation from a TOML
file, and the same data exposed to Claude through MCP so it pulls real numbers instead of
making them up. Data is delayed Yahoo data. Not investment advice.

## Install

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/lisaperrin/marketlens
cd marketlens
uv sync
uv run marketlens --help
```

## Usage

```bash
marketlens quote AAPL MSFT
marketlens analyze NVDA --period 6mo
marketlens compare AAPL MSFT VTI
marketlens portfolio                     # reads ./portfolio.toml
marketlens brief --watchlist AAPL,MSFT --portfolio portfolio.toml
marketlens alerts --portfolio portfolio.toml --rules alerts.toml
marketlens cache stats
```

`--json` before the command gives JSON. `--no-cache` skips the local cache.

Periods: `1mo 3mo 6mo 1y 2y 5y max`.

### Optional flags

```bash
marketlens analyze NVDA -b SPY           # benchmark return, excess return, beta
marketlens compare AAPL MSFT -b VWCE.DE  # Excess and Beta columns
marketlens portfolio -b VWCE.DE          # benchmark day move + weighted portfolio beta
marketlens analyze NVDA --indicators     # EMA 20, MACD, Bollinger Bands
```

Benchmark stats use the trading days both series have in common. The analyze panel shows a
"Signals" row when the close is outside the Bollinger Bands, MACD or SMA 50/200 crossed in
the last 5 sessions, or RSI is past 70/30. Otherwise the row isn't there.

### portfolio.toml

```toml
base_currency = "EUR"
benchmark = "VWCE.DE"      # optional, used by `portfolio` only

[[holdings]]
symbol = "ALV.DE"
shares = 5
cost_basis = 250.00        # avg price paid per share
```

Use the ticker of the listing you bought (e.g. `ABEA.DE` for Alphabet on Xetra). There is no
FX conversion, so mixed currencies will add up to nonsense. The file is gitignored.

### alerts.toml

```toml
[defaults]
rsi_above = 70
rsi_below = 30
day_change_abs = 5.0       # percent
bollinger = true

[[rules]]
symbol = "NVD.DE"
price_below = 120.0
price_above = 200.0
```

`alerts` prints only what fired. Symbols it can't fetch are listed as skipped; the rest still
run. `--fail-on-alert` exits 3 if anything fired (for cron). See
`examples/alerts.example.toml`.

## Claude Code

```text
/plugin install marketlens --marketplace lisaperrin/marketlens
```

Installs:

- MCP server `marketlens` with `get_quote`, `analyze_ticker`, `compare_tickers`,
  `portfolio_summary`, `market_brief`, `check_alerts`, `get_statements`. Started with
  `uvx` from the plugin directory, so uv has to be on PATH. First start takes a minute.
- Skills: `/marketlens:analyze-ticker`, `compare-tickers`, `portfolio-review`,
  `market-brief`, `check-alerts`. `add-indicator` is for working on this repo.
- Agents: `market-analyst` (research notes from live data), `quant-reviewer` (checks
  indicator maths and tests).
- Hooks: one prints the tool list at session start, one spots `$TICKER` in a prompt and
  tells Claude to use the tools instead of recalling prices.

## Layout

```text
src/marketlens/
  data/         MarketDataProvider protocol, YFinanceProvider, CachedProvider (sqlite), FakeProvider
  analysis/     indicators.py (SMA, EMA, RSI, MACD, Bollinger), stats.py (returns, vol, drawdown,
                Sharpe, beta, correlation), summary.py (TickerSummary, signals)
  portfolio/    holdings.py (TOML), valuation.py
  alerts/       rules.py (TOML), engine.py
  report/       rich tables, brief
  cli.py        Typer
  mcp_server.py MCPServer, same functions as the CLI
```

All data access goes through `MarketDataProvider`. `CachedProvider` wraps any provider
with a SQLite cache (quotes 15 min, history 1 h, fundamentals and statements 24 h).
`FakeProvider` serves fixed frames; tests never hit the network.

Conventions, since they bite otherwise:

- `total_return`, `annualized_volatility`, `max_drawdown`, `pnl_pct`, `weight` are
  fractions. `change_pct`, `day_change_pct`, `dividend_yield` are percentages.
- `None` means Yahoo didn't have it. Nothing is estimated or filled in.
- RSI is Wilder smoothing. Volatility is sample std × √252. Beta is cov/var of daily
  returns on an inner join of dates, `None` under 3 shared points.
- Errors subclass `MarketLensError`. CLI prints one line and exits 1. MCP raises `ToolError`.

`get_statements(symbol, years=4)` (library and MCP, no CLI command) returns per-fiscal-year
balance sheet / income / cash flow lines: net PPE, capex (as a positive number), R&D,
SG&A, total debt, cash, shares outstanding, close at year end. Oldest first, as reported.
Written for [firmvalue](https://github.com/lisaperrin/firm-value-decomposition), which uses
this package as its data source. `STATEMENT_FIELDS` has the field names. If you type
against `Statements` with a `Protocol`, use read-only properties; frozen dataclass fields
don't satisfy settable attributes under strict mypy.

## Development

```bash
uv sync --all-groups
uv run pytest -q                                  # ~225 tests, offline, ~3 s
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run python scripts/validate_plugin.py --with-claude-cli
```

ruff, line length 100. mypy strict. pytest treats warnings as errors. CI runs on 3.12 and
3.13. Every indicator and statistic has a test with a value computed by hand; see
`tests/analysis/`. `.claude/settings.json` has two hooks for people working on this in
Claude Code: ruff after every edit, and a block on `git push --force`, `--no-verify` and
`git reset --hard`.

Design notes and the plans I worked from: `docs/design.md`, `docs/plan.md`,
`docs/plan-0.2.md`.

## Changelog

- 0.3.1: cache rows written by an older version of a model are refetched instead of decoded
  with missing fields (0.3.0 could report `employees=None` from a 0.2.0 cache for a day).
- 0.3.0: `get_statements`, `Fundamentals.employees`, `py.typed`.
- 0.2.0: benchmark comparison, EMA/MACD/Bollinger + signals, `alerts`.
- 0.1.0: provider + cache, analysis, portfolio, CLI, MCP server, plugin.

## Known gaps

No FX. No intraday. No backtests. Headcount is a single latest number (yfinance has no
history). Yahoo line names differ for banks and insurers, so some statement fields come back
`None` there.

## License

MIT. Yahoo data via yfinance, subject to
[Yahoo's terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html). Not affiliated
with Yahoo.
