---
name: market-brief
description: Produce a short daily market brief for a watchlist, with the biggest movers and an optional portfolio snapshot. Use for "what happened today", morning check-ins, or a quick scan of a list of tickers.
argument-hint: [SYMBOL,SYMBOL,...] [--portfolio path]
allowed-tools: mcp__plugin_marketlens_marketlens__market_brief Bash(uv run marketlens *)
---

# Market brief

Write a brief for the watchlist in `$ARGUMENTS`.

## Steps

1. **Resolve the watchlist.** Symbols may be comma or space separated. If none are given and a
   `portfolio.toml` exists in the project, use its symbols; otherwise ask for a list and stop.
   A trailing `--portfolio <path>` includes a portfolio snapshot.
2. **Fetch.** Call the `market_brief` MCP tool with `symbols=[...]` and `portfolio_path` when
   given. Fallback: `uv run marketlens --json brief --watchlist A,B --portfolio <path>`.
3. **Write the brief**, under 150 words:
   - Headline: the top and bottom mover with their day-change percentages.
   - One line per symbol: price and day change, grouped as gainers then losers.
   - If a portfolio was included: total value, today's move in currency and percent.
4. **Timestamp** the brief with `generated_at` from the output, and end with
   "Delayed data, not investment advice."

## Rules

- A brief is a scan, not an analysis. Do not speculate about why something moved unless the
  user asks; offer `/marketlens:analyze-ticker <SYMBOL>` for depth.
- Day changes are already percentages in the tool output.
