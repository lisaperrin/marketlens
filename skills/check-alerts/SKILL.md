---
name: check-alerts
description: Check a watchlist or portfolio for crossed thresholds (RSI extremes, big day moves, price levels, Bollinger breakouts) and report only what fired. Use for "anything I should look at today", "did anything cross", or scheduled check-ins.
argument-hint: [SYMBOL,SYMBOL,...] [--portfolio path] [--rules alerts.toml]
allowed-tools: mcp__plugin_marketlens_marketlens__check_alerts mcp__plugin_marketlens_marketlens__analyze_ticker Read Bash(uv run marketlens *)
---

# Check alerts

Report thresholds crossed for the symbols in `$ARGUMENTS`.

## Steps

1. **Resolve inputs.** Comma or space separated symbols are the watchlist; `--portfolio <path>`
   adds every holding; `--rules <path>` loads per-symbol thresholds. With none of the three,
   look for `portfolio.toml` and `alerts.toml` in the project root; if neither exists, ask for a
   watchlist and stop.
2. **Evaluate.** Call the `check_alerts` MCP tool with `symbols=[...]`, `rules_path` and
   `portfolio_path` when given. Fallback: `uv run marketlens --json alerts -w A,B --portfolio <p>`.
3. **Report.** If `alerts` is empty: one line, "No alerts across N symbols", and stop.
   Otherwise one bullet per alert, grouped by symbol, quoting the tool's `message` and adding
   at most one sentence of context. Order: price levels first, then day moves, RSI, Bollinger.
4. **Offer depth, do not force it.** For at most the two most significant alerts, offer
   `/marketlens:analyze-ticker <SYMBOL>`; call `analyze_ticker` yourself only if the user asked
   for analysis in the same message.
5. End with the timestamp and "Delayed data, not investment advice."

## Default thresholds

RSI 14 at or above 70 or at or below 30; absolute day change of 5 % or more; close outside
the 20-day, 2-standard-deviation Bollinger Bands. `alerts.toml` (see
`examples/alerts.example.toml`) changes defaults and adds `price_above` / `price_below` per
symbol.

## Rules

- An alert is a prompt to look, not a recommendation. Never turn one into "sell" or "buy".
- `day_change_abs` and the RSI values are already in their natural units (percent, index
  points); do not rescale them.
