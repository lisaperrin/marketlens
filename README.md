# MarketLens

Stock market research from the terminal and from Claude Code, built on
[yfinance](https://github.com/ranaroussi/yfinance).

[![CI](https://github.com/lisaperrin/marketlens/actions/workflows/ci.yml/badge.svg)](https://github.com/lisaperrin/marketlens/actions/workflows/ci.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

I wrote MarketLens because I wanted three things in one place: a quick read on a single
stock, a fair comparison between a few of them, and an honest view of my own depot, which
is a mix of German, US and ETF positions quoted in euros. Along the way it became a small
case study in building a data layer once and exposing it three ways: a typed Python
library, a command line tool, and an MCP server that Claude can call, packaged as a
Claude Code plugin so the same numbers show up whether I am in a terminal or in a chat.

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

Yahoo's data is delayed and nothing this tool prints is investment advice. It tells you
what the numbers are; what to do about them is your call.

## Getting started

You need Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/lisaperrin/marketlens && cd marketlens
uv sync
uv run marketlens quote AAPL MSFT
uv run marketlens analyze NVDA --period 6mo
uv run marketlens compare AAPL MSFT VTI
uv run marketlens brief --watchlist AAPL,MSFT,NVDA
```

Put `--json` in front of any command for machine-readable output, `--no-cache` to go
straight to Yahoo. The cache lives in `$XDG_CACHE_HOME/marketlens/cache.db`; `marketlens
cache stats` and `marketlens cache clear` manage it.

### Your portfolio

Holdings live in a small TOML file that stays on your machine (`portfolio.toml` is in
`.gitignore`). Copy `examples/portfolio.example.toml` and fill in what you own:

```toml
base_currency = "EUR"
benchmark = "VWCE.DE"          # optional

[[holdings]]
symbol = "ALV.DE"
shares = 5
cost_basis = 250.00            # average price paid per share
```

`uv run marketlens portfolio` then prints each position with market value, profit and
loss, weight and today's move, plus totals. Use the ticker of the exchange you actually
bought on (`ABEA.DE` for Alphabet on Xetra, not `GOOGL`) so prices and your cost basis are
in the same currency; the tool does not convert currencies.

### The parts you have to ask for

By default `analyze`, `compare` and `portfolio` print the same panels they always have.
A few things are switched on explicitly, because they are only useful when you want them:

```bash
uv run marketlens analyze NVDA --benchmark SPY     # benchmark return, excess return, beta
uv run marketlens compare AAPL MSFT -b VWCE.DE     # adds Excess and Beta columns
uv run marketlens portfolio -b VWCE.DE             # benchmark day move, portfolio beta
uv run marketlens analyze NVDA --indicators        # EMA 20, MACD, Bollinger Bands
uv run marketlens alerts --portfolio portfolio.toml --rules alerts.toml
```

Beta and excess return are computed over the trading days both series share, so a
benchmark with a shorter history does not quietly distort the comparison. The analyze
panel adds a *Signals* row on its own only when there is something to say: a close outside
the Bollinger Bands, a MACD or SMA 50/200 crossover within the last five sessions, or an
RSI beyond 70 or 30. A line that flickers around zero is not reported as a crossover.

`alerts` is the piece I run from cron. It prints only what crossed a threshold (RSI 70/30,
a day move of five percent or more, Bollinger breakouts, and any per-symbol price levels
from `alerts.toml`), names symbols it could not fetch instead of aborting, and with
`--fail-on-alert` exits with code 3 so a shell script can decide what to do next.

## From Claude Code

The repository doubles as a Claude Code plugin. Inside Claude Code:

```text
/plugin install marketlens --marketplace lisaperrin/marketlens
```

That gives Claude an MCP server with seven tools (`get_quote`, `analyze_ticker`,
`compare_tickers`, `portfolio_summary`, `market_brief`, `check_alerts`, `get_statements`),
five user-facing skills (`/marketlens:analyze-ticker`, `compare-tickers`,
`portfolio-review`, `market-brief`, `check-alerts`), two agents (`market-analyst` for
multi-step research notes, `quant-reviewer` for checking indicator maths against textbook
definitions), and two hooks. One hook announces the tools at session start; the other
notices cashtags like `$NVDA` in a prompt and reminds Claude to call the live tools instead
of quoting prices from memory. The server starts via `uvx` from the installed plugin
folder, so there is nothing to configure beyond having uv on your PATH.

The skills are deliberately opinionated about honesty: fractions versus percentages are
spelled out, `None` is reported as "not available" rather than guessed, and every note ends
with the data timestamp.

## How it is built

```text
src/marketlens/
├── data/          provider protocol, yfinance provider, SQLite cache, fake provider for tests
├── analysis/      pure functions on a Close series: returns, risk, beta, SMA/EMA, RSI, MACD, Bollinger
├── portfolio/     TOML holdings loader, valuation, benchmark comparison
├── alerts/        threshold rules (TOML) and evaluation
├── report/        rich tables and the daily brief; to_dict() feeds --json and MCP
├── cli.py         Typer commands
└── mcp_server.py  the same operations as MCP tools
```

Everything that touches Yahoo goes through one `MarketDataProvider` protocol. The real
implementation wraps yfinance; a caching decorator stores results in SQLite with
per-kind lifetimes (quotes 15 minutes, price history an hour, fundamentals and annual
statements a day); and a `FakeProvider` serves canned frames so the whole test suite,
including the MCP tools and the shell hooks, runs offline in about three seconds. The
cache survives corrupted files by moving them aside, and every yfinance transport failure
is turned into one readable error rather than a traceback.

The analysis package is where I was most careful. Each statistic has a known-answer test
with a value worked out by hand: RSI uses Wilder's smoothing and is checked against a
two-period example you can verify on paper, volatility is sample standard deviation
scaled by the square root of 252, drawdown is a negative fraction, beta is the covariance
of daily returns over the benchmark's variance on an inner join of dates. Where a function
cannot produce a meaningful number (a constant series, too few points, no overlapping
dates) it returns `None` and the tables print a dash.

Models are frozen dataclasses. The CLI and the MCP server are thin: both call the same
functions and the same `to_dict()` methods, which is why `--json` output and tool output
never drift apart.

The design notes for each release are in [`docs/design.md`](docs/design.md), with the
task-by-task plans next to them. They are the documents I actually built from, not
after-the-fact write-ups.

## History

**0.1** was the core: provider and cache, the analysis functions, portfolio valuation,
the CLI, the MCP server and the plugin, with CI on Python 3.12 and 3.13.

**0.2** added the opt-in features above: benchmark comparison, EMA, MACD and Bollinger
Bands with the signals logic, and the alerts command. The rule for this release was that
default output must not change; the test suite asserts the absence of the new rows and
columns when the options are off.

**0.3** added `get_statements`, which returns annual balance sheet, income statement and
cash flow lines per fiscal year (net PPE, capex, R&D, SG&A, gross debt, cash, shares
outstanding and the year-end close) exactly as Yahoo publishes them. I built it for
[firmvalue](https://github.com/lisaperrin/firm-value-decomposition), a structural
decomposition of firm value that uses MarketLens as its live data layer. Agreeing the
record shape with a downstream consumer before writing it, and shipping `STATEMENT_FIELDS`
so the consumer can schema-check at import time, was a useful exercise in treating a
dataclass as an interface.

## Limitations

Yahoo is a free, delayed source with occasional gaps; the tool reports gaps rather than
filling them. There is no currency conversion, no intraday data, no backtesting and no
order execution, and none of those are planned. Headcount comes as a single latest value
because yfinance keeps no history for it.

## Development

```bash
uv sync --all-groups
uv run pytest -q
uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run python scripts/validate_plugin.py --with-claude-cli
```

Ruff at 100 columns, mypy in strict mode, pytest with warnings turned into errors.
Two project hooks in `.claude/settings.json` format Python files after each edit and refuse
`git push --force`, `--no-verify` and `git reset --hard`. Conventional commit messages.
If you type against `Statements` structurally with a `Protocol`, declare its members as
read-only properties; frozen-dataclass fields are read-only and strict mypy will tell you.

## Licence

MIT. Market data comes from Yahoo Finance through yfinance and is subject to
[Yahoo's terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html). This project
is not affiliated with Yahoo.
