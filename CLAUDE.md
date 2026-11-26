# MarketLens

Python 3.12+ toolkit for stock market research on yfinance, plus the Claude Code plugin in
this same repository (`.claude-plugin/`, `skills/`, `agents/`, `hooks/`, `.mcp.json`).

## Commands

- `uv sync --all-groups` installs everything.
- `uv run pytest -q` runs the suite (fast, fully offline; no test may touch the network).
- `uv run ruff check . && uv run ruff format --check . && uv run mypy` is the lint gate.
- `uv run marketlens --help` is the CLI; `uv run marketlens-mcp` starts the MCP server.
- `uv run python scripts/validate_plugin.py` checks the plugin files are coherent.

## Architecture (see docs/design.md)

- `data/`: `MarketDataProvider` protocol, `YFinanceProvider`, `CachedProvider` (SQLite),
  `FakeProvider` for tests. All market data enters through a provider.
- `analysis/`: pure functions over a `Close` series. No provider access here.
- `portfolio/`: TOML holdings loader and valuation.
- `report/`: rich tables and the daily brief; `to_dict()` methods feed `--json` and MCP.
- `cli.py` and `mcp_server.py` are thin; logic lives in the packages above.

## Conventions

- Test-first. Every indicator or statistic has a known-answer test with hand-computed values.
- Fractions versus percentages: `total_return`, `annualized_volatility`, `max_drawdown`,
  `pnl_pct` are fractions; `change_pct`, `day_change_pct`, `dividend_yield` are percentages.
- Errors derive from `MarketLensError`; the CLI exits 1 with one line, MCP raises `ToolError`.
- Frozen dataclasses for models. `None` means "not available"; never invent a number.
- Conventional commit messages (`feat(data): ...`, `fix(cli): ...`).
- Hooks in `.claude/settings.json` auto-format Python after edits and block force-pushes and
  `--no-verify`; do not work around them.
