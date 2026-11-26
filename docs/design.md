# MarketLens — Design

**Date:** 2026-11-26 · **Status:** approved for build

## Intent

A clean, well-tested Python toolkit for following the stock market with
[yfinance](https://github.com/ranaroussi/yfinance) as the data source, packaged
together with a complete Claude Code plugin (skills, agents, hooks and an MCP
server) so Claude can research tickers, compare them and review a portfolio
from inside a coding session.

It exists to be two things at once: a genuinely useful daily market tool, and a
showcase of how a Python project and a Claude Code integration should be built.

## Goals

- Answer the three everyday questions quickly: *how is this ticker doing*,
  *how do these tickers compare*, and *how is my portfolio doing*.
- Deterministic, offline tests. Nothing in the test suite touches the network.
- One source of truth for market data (a provider interface) that the CLI, the
  MCP server and the Claude skills all share.
- Reusable Claude Code plugin: install it in any project and get the skills,
  agents and MCP tools.

## Non-goals

- Trading or order execution of any kind.
- Backtesting engine or strategy optimisation.
- Real-time streaming quotes. Yahoo's delayed data is enough.
- Multi-currency conversion. Holdings are valued in their quoted currency and
  summed in a single base currency the user declares.

## Anti-goals (what would make this a failure)

- Analysis functions whose maths is not pinned by a known-answer test.
- A plugin that only works when the repo is open (skills must work installed).
- Hitting Yahoo on every call. Caching is part of the design, not a nice-to-have.

## Constraints

- Python 3.12+, managed with **uv** (committed `uv.lock`, `uv run` for every
  command, `uvx` to launch the MCP server from the plugin).
- Dependencies kept small: `yfinance`, `pandas`, `typer`, `rich`, `mcp`.
  Dev: `pytest`, `ruff`, `mypy`.
- Licence MIT.

## Approaches considered

1. **Thin scripts + Claude skills only.** Fastest, but every skill would call
   yfinance ad hoc, tests would need the network, and nothing would be reusable.
   Rejected: fails the "offline tests" and "one source of truth" goals.
2. **Library + CLI, with Claude skills shelling out to the CLI.** Solid and
   simple. Claude gets structured output through `--json`. Lacks a first-class
   MCP integration, which is the most natural "finance connection" for Claude.
3. **Library + CLI + MCP server, wrapped as a plugin** *(chosen)*. The same
   `MarketDataProvider` feeds the CLI and the MCP server; skills prefer the MCP
   tools and fall back to the CLI. Costs one extra module (`mcp_server.py`) and
   buys the cleanest Claude integration and the strongest showcase.

## Architecture

```
src/marketlens/
  data/        provider Protocol · yfinance provider · SQLite cache · fake provider
  analysis/    pure pandas functions: returns, volatility, drawdown, SMA, RSI, Sharpe, correlation
  portfolio/   holdings TOML loader · valuation (value, P&L, weights, day change)
  report/      rich tables for the terminal · plain dicts for --json and MCP
  cli.py       Typer app: quote · analyze · compare · portfolio · brief · cache
  mcp_server.py FastMCP stdio server exposing the same operations as tools
```

Plugin layer at the repo root (so the repo itself is installable):

```
.claude-plugin/plugin.json   manifest        .claude-plugin/marketplace.json  self-hosted marketplace
skills/      analyze-ticker · compare-tickers · portfolio-review · market-brief · add-indicator
agents/      market-analyst · quant-reviewer
hooks/       hooks.json + scripts/ (SessionStart cache status, UserPromptSubmit ticker hint)
.mcp.json    launches `marketlens-mcp` via uvx
.claude/settings.json  project hooks for contributors: ruff on edit, guard risky git commands
```

### Key decisions

- **Provider Protocol + fake.** `MarketDataProvider` is a `typing.Protocol`;
  `FakeProvider` serves canned frames so every test is deterministic.
- **Cache.** `CachedProvider` wraps any provider and stores results in SQLite at
  `$XDG_CACHE_HOME/marketlens/cache.db`. TTLs: quotes 15 min, history 1 h,
  fundamentals 24 h. `--no-cache` bypasses it.
- **Models are frozen dataclasses** (`Quote`, `Fundamentals`, `TickerSummary`,
  `Holding`, `Position`, `PortfolioValuation`). Price history is a pandas
  DataFrame with a `DatetimeIndex` and columns `Open High Low Close Volume`.
- **Analysis functions take a `Close` Series and return floats or Series.**
  No provider access inside analysis: easy to test, easy to reuse.
- **Holdings file** is TOML: `base_currency` plus `[[holdings]]` entries with
  `symbol`, `shares`, `cost_basis` (per share).
- **Errors** are `MarketLensError` subclasses: `SymbolNotFoundError`,
  `DataUnavailableError`, `HoldingsFileError`. The CLI maps them to exit code 1
  with a one-line message; the MCP server returns them as tool errors.

## Left to the builder

- Exact rich table styling.
- Column order in JSON output, as long as field names match the dataclasses.

---

# v0.2 additions — benchmark, indicators, alerts

**Date:** 2026-11-26 · **Status:** approved for build

## Principle

Nothing new appears in default output unless the user asks for it or it says something.
Today's `analyze`, `compare` and `portfolio` output is unchanged when no new option is used.

## 1. Benchmark (opt-in)

- `--benchmark SYMBOL` / `-b` on `analyze`, `compare` and `portfolio`; MCP tools take an
  optional `benchmark` argument. `portfolio.toml` may set `benchmark = "VWCE.DE"` as the
  default for the portfolio view only.
- Per ticker, over the same period: benchmark total return, **excess return** (ticker minus
  benchmark) and **beta** (covariance of daily returns over benchmark variance, aligned on
  shared dates). Shown as extra rows in the analyze panel and extra columns in compare.
- Per portfolio: benchmark day change next to the portfolio day change, and a
  **weighted beta** (sum of position weight × position beta over the period). Shown as one
  line under the portfolio table. Portfolio return since purchase is *not* compared, because
  purchase dates are unknown.

## 2. Indicators (EMA, MACD, Bollinger Bands)

- Pure functions in `analysis/indicators.py`: `ema(close, span)`, `macd(close, 12, 26, 9)`
  returning a frame with `macd`, `signal`, `histogram`; `bollinger(close, 20, 2.0)` returning
  `middle`, `upper`, `lower`. Known-answer tests for each.
- `TickerSummary.indicators` holds the latest values (always in JSON and MCP output);
  `analyze --indicators` renders them as a second block in the terminal.
- `TickerSummary.signals` is a tuple of short sentences that are only produced when notable:
  price outside the Bollinger bands, MACD crossing its signal line within the last 5 sessions,
  RSI above 70 or below 30, SMA 50 crossing SMA 200 within the last 5 sessions. The panel shows
  a "Signals" row only when the tuple is non-empty.

## 3. Alerts

- `marketlens alerts [--watchlist A,B] [--portfolio portfolio.toml] [--rules alerts.toml]`
  prints only what crossed, one line per alert, and nothing (plus a "no alerts" line) otherwise.
  `--json` returns `{"symbols": [...], "alerts": [...], "errors": [...]}` so a script knows what
  was checked and which symbols could not be fetched. Exit code is 0 either way;
  `--fail-on-alert` returns 3 when anything fired, for cron use.
- Default rules for every symbol: RSI ≥ 70 or ≤ 30; absolute day change ≥ 5 %; close outside
  the Bollinger bands. `alerts.toml` overrides or adds per-symbol thresholds:

  ```toml
  [defaults]
  rsi_above = 70
  rsi_below = 30
  day_change_abs = 5.0        # percent

  [[rules]]
  symbol = "NVD.DE"
  price_below = 120.0
  price_above = 200.0
  ```

- New MCP tool `check_alerts(symbols, rules_path=None, portfolio_path=None)`; the
  `market-brief` skill mentions it; a new `check-alerts` skill wraps it.

## Non-goals (still)

No scheduled delivery, no persistence of fired alerts, no notifications. `alerts` is the
building block a cron job or a later delivery feature calls.
