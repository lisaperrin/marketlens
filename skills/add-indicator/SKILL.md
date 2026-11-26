---
name: add-indicator
description: Add a new technical indicator or statistic to MarketLens the project way, test-first with a known-answer test. Use when working inside the MarketLens repository and asked to add, say, EMA, MACD, Bollinger Bands or Sortino ratio.
argument-hint: <indicator name> [parameters]
disable-model-invocation: true
---

# Add an indicator

Implement **$ARGUMENTS** in the MarketLens analysis package following the project's rules.

## Where things live

- `src/marketlens/analysis/indicators.py`: series-valued indicators (SMA, RSI). Each takes
  a `Close` series and returns a series aligned to the same index, `NaN` until the window fills.
- `src/marketlens/analysis/stats.py`: scalar statistics (total return, volatility, drawdown,
  Sharpe). Each takes a `Close` series and returns a `float`.
- `src/marketlens/analysis/summary.py`: `TickerSummary` carries the headline values exposed by
  the CLI and MCP server. Add a field here only if the indicator is worth showing by default.
- Tests mirror the layout under `tests/analysis/`.

## Steps

1. **Write the known-answer test first** in the matching test file. Use a tiny hand-computable
   series (five to ten points) and assert the exact expected value with `pytest.approx`.
   Include one edge case: a series shorter than the window must give `NaN`/`None`, never raise.
2. **Run it and watch it fail**: `uv run pytest tests/analysis -q`.
3. **Implement** the smallest function that passes. Validate `window >= 1` with `ValueError`,
   as `sma` does. No provider access inside analysis code.
4. **Export it** from `src/marketlens/analysis/__init__.py` (keep `__all__` sorted).
5. **Wire it up only if asked**: add a field to `TickerSummary`, compute it in
   `_summarize_with_close`, show it in `report/tables.py`, and extend the summary tests.
6. **Gate**: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q`.
7. **Ask the `quant-reviewer` agent** to check the maths before committing.

## Rules

- Docstrings state the formula and the convention (fraction versus percent).
- Never change an existing indicator's output to make a new test pass.
