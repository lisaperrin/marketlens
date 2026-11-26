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
- Licence MIT. Private GitHub repo to start.

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
