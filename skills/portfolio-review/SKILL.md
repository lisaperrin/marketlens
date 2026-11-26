---
name: portfolio-review
description: Value a holdings file and review concentration, winners, losers and day moves. Use when the user asks how their portfolio is doing, wants a P&L check, or asks whether they are too concentrated.
argument-hint: [path/to/portfolio.toml]
allowed-tools: mcp__plugin_marketlens_marketlens__portfolio_summary mcp__plugin_marketlens_marketlens__analyze_ticker Read Bash(uv run marketlens *)
---

# Portfolio review

Review the holdings file at `$0` (default `./portfolio.toml`) with live prices.

## Steps

1. **Locate the file.** If `$0` is empty use `portfolio.toml` in the project root. If it does
   not exist, show the user the format below and offer to create one from their holdings.
   Do not guess their positions.
2. **Value it.** Call the `portfolio_summary` MCP tool with the absolute path. Fallback:
   `uv run marketlens --json portfolio <path>`.
3. **Summarise the headline** in one line: total value, total P&L (absolute and percent),
   and today's move.
4. **Positions table**, sorted by weight descending:

   | Symbol | Weight | Value | P&L | P&L % | Day % |

5. **Concentration check.** Flag any position above 25 % of the portfolio and note how much
   of the total the top three positions make up.
6. **Winners and losers.** Name the best and worst position by P&L percent, and the biggest
   mover today.
7. **Optional depth.** If the user asked about a specific holding, or one position dominates
   today's move, call `analyze_ticker` on it and add two sentences of context.
8. End with: "Delayed data, not investment advice."

## Benchmark

If the holdings file sets `benchmark = "..."`, or the user asks how the portfolio did against
the market, pass `benchmark` to the tool and add one sentence: the benchmark's day move next
to the portfolio's, and the portfolio's weighted beta (above 1 means it swings more than the
benchmark). Do not compare return since purchase; purchase dates are unknown.

## Holdings file format

```toml
base_currency = "USD"
benchmark = "VTI"     # optional

[[holdings]]
symbol = "AAPL"
shares = 10
cost_basis = 150.00   # average price paid per share
```

## Rules

- Percent conventions in the tool output: `pnl_pct`, `total_pnl_pct` and `weight` are
  fractions (`0.20` is 20 %); `day_change_pct` is already a percentage (`2.86` is 2.86 %).
- Holdings are personal data. Do not paste the file into chat beyond what the review needs,
  and never write it to a location outside the project.
- Valuation ignores currency conversion; say so if positions quote in different currencies.
