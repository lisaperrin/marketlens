# MarketLens

[![CI](https://github.com/lisaperrin/marketlens/actions/workflows/ci.yml/badge.svg)](https://github.com/lisaperrin/marketlens/actions/workflows/ci.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-8A2BE2)

Stock market research from the terminal and from Claude Code, powered by
[yfinance](https://github.com/ranaroussi/yfinance).

MarketLens answers three everyday questions: **how is this ticker doing**, **how do these
tickers compare**, and **how is my portfolio doing**. It is a typed Python library with a
CLI, a [Model Context Protocol](https://modelcontextprotocol.io) server, and a complete
Claude Code plugin (skills, agents and hooks) that all share one data layer.

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

## Quickstart (60 seconds)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
git clone https://github.com/lisaperrin/marketlens && cd marketlens
uv sync
uv run marketlens quote AAPL MSFT
uv run marketlens analyze NVDA --period 6mo
uv run marketlens compare AAPL MSFT VTI
uv run marketlens portfolio examples/portfolio.example.toml
uv run marketlens brief --watchlist AAPL,MSFT,NVDA
```

Add `--json` before any command for machine-readable output, `--no-cache` to bypass the
local cache. Yahoo data is delayed and nothing here is investment advice.

### Your own portfolio

Copy `examples/portfolio.example.toml` to `portfolio.toml` (git-ignored) and edit:

```toml
base_currency = "USD"

[[holdings]]
symbol = "AAPL"
shares = 10
cost_basis = 150.00   # average price paid per share
```

Then `uv run marketlens portfolio`.

## Use it from Claude Code

The repository is itself a Claude Code plugin. Install it in one step:

```text
/plugin install marketlens --marketplace lisaperrin/marketlens
```

Or in two: `/plugin marketplace add lisaperrin/marketlens` then
`/plugin install marketlens@marketlens-marketplace`.

The MCP server is launched with `uvx` from the installed plugin folder, so
[uv](https://docs.astral.sh/uv/) must be on your PATH. The first launch builds the server's
environment and can take a minute; later launches are instant.

What you get:

| Component | Name | What it does |
|-----------|------|--------------|
| MCP server | `marketlens` | Tools `get_quote`, `analyze_ticker`, `compare_tickers`, `portfolio_summary`, `market_brief`. Launched with `uvx` from the plugin folder, so no manual setup. |
| Skill | `/marketlens:analyze-ticker AAPL [1y]` | Structured research note on one symbol. |
| Skill | `/marketlens:compare-tickers AAPL MSFT` | Side-by-side table, correlation and a verdict. |
| Skill | `/marketlens:portfolio-review [path]` | Valuation, concentration, winners and losers. |
| Skill | `/marketlens:market-brief NVDA,TSLA` | Sub-150-word daily brief with movers. |
| Skill | `/marketlens:add-indicator EMA 20` | Dev workflow: add an indicator test-first (repo only). |
| Agent | `market-analyst` | Multi-call research write-ups from live data; never quotes from memory. |
| Agent | `quant-reviewer` | Checks indicator maths and tests against textbook definitions. |
| Hook | `SessionStart` | Announces the tools so Claude reaches for live data. |
| Hook | `UserPromptSubmit` | Detects cashtags like `$AAPL` and nudges Claude to the MCP tools. |

Ask naturally: *"how has $NVDA done against $AMD this year?"* and Claude will call the
tools instead of guessing.

## Architecture

```text
src/marketlens/
├── data/          MarketDataProvider protocol · YFinanceProvider · CachedProvider (SQLite) · FakeProvider
├── analysis/      pure pandas: returns, volatility, drawdown, Sharpe, SMA, RSI, correlation, summaries
├── portfolio/     TOML holdings loader · valuation (value, P&L, weights, day change)
├── report/        rich tables and the daily brief; to_dict() feeds --json and MCP
├── cli.py         Typer: quote · analyze · compare · portfolio · brief · cache
└── mcp_server.py  MCP stdio server exposing the same operations as tools

.claude-plugin/    plugin.json and marketplace.json        skills/  agents/  hooks/   plugin components
.mcp.json          MCP server launch config                .claude/ project hooks and permissions
```

Design notes live in [`docs/design.md`](docs/design.md); the task-by-task build plan in
[`docs/plan.md`](docs/plan.md).

Key decisions:

- **One provider interface.** Everything reads market data through `MarketDataProvider`.
  `CachedProvider` wraps any provider with a SQLite cache (quotes 15 min, history 1 h,
  fundamentals 24 h) at `$XDG_CACHE_HOME/marketlens/cache.db`.
- **Offline tests.** `FakeProvider` serves canned frames; the whole suite runs in two seconds
  without a network connection, including the MCP tools and the hook scripts.
- **Known-answer maths.** Every statistic is pinned by a hand-computed test. RSI uses Wilder
  smoothing, volatility uses sample standard deviation scaled by sqrt(252), drawdown is a
  negative fraction.
- **Readable failures.** All errors derive from `MarketLensError`; the CLI exits 1 with one
  line, the MCP server raises a `ToolError` carrying the message, and yfinance's transport
  failures become `DataUnavailableError` instead of tracebacks.

## Development

```bash
uv sync --all-groups
uv run pytest -q                      # whole suite, offline, a few seconds
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run python scripts/validate_plugin.py --with-claude-cli
```

Contributors working in Claude Code get two project hooks from `.claude/settings.json`:
every edited Python file is formatted with ruff, and `git push --force`, `--no-verify` and
`git reset --hard` are refused. CI runs lint, types and tests on Python 3.12 and 3.13.

## Licence

MIT. Market data is provided by Yahoo Finance through yfinance and is subject to
[Yahoo's terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html); this project is
not affiliated with Yahoo.
