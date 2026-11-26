---
name: analyze-ticker
description: Research one stock or ETF with live data. Use when the user asks how a ticker is doing, whether it looks expensive, how volatile it has been, or for a quick read on a symbol.
argument-hint: <SYMBOL> [period]
allowed-tools: mcp__plugin_marketlens_marketlens__analyze_ticker mcp__plugin_marketlens_marketlens__get_quote Bash(uv run marketlens *)
---

# Analyze a ticker

Produce a short, honest research note on **$0** using live market data.
The optional second argument is the history window (`1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`,
`max`); default to `1y` when `$1` is empty.

## Steps

1. **Fetch the data.** Call the `analyze_ticker` MCP tool with `symbol="$0"` and the chosen
   period. If the MCP server is unavailable, run `uv run marketlens --json analyze $0 --period <p>`
   instead. Never fill in numbers from memory.
2. **If the tool reports an unknown symbol**, say so and suggest the two or three most likely
   intended tickers. Stop there.
3. **Read the numbers before writing.** Note the sign of the total return, where price sits
   against SMA 50 and SMA 200, whether RSI is above 70 or below 30, the size of the max
   drawdown, and the valuation (trailing and forward P/E, dividend yield) in the context of
   the sector.
4. **Write the note** in this shape, in prose, no more than 250 words:
   - One line: price, day change, currency, and the period's total return.
   - Trend: price versus the two moving averages and what RSI says about momentum.
   - Risk: annualised volatility and max drawdown, in plain words.
   - Valuation: P/E and yield, compared with what is typical for the sector if you know it.
   - Two things worth watching next, drawn from the data (for example an RSI extreme or a
     price near the 52-week high).
5. **Close with the data timestamp** and the sentence: "Delayed data, not investment advice."

## Benchmark (only when asked)

If the user asks how the stock did "against the market", "vs the index" or names a benchmark,
pass `benchmark="<SYMBOL>"` (SPY for US large caps, VWCE.DE for a global EUR view, or what the
user named). Report the benchmark return, the excess return and beta in one sentence each.
Do not add a benchmark otherwise.

## Rules

- Percentages in the tool output are fractions (`0.12` is 12 %) except `change_pct`,
  `day_change_pct` and `dividend_yield`, which are already percentages.
- `None` means the data was unavailable; say "not available", do not invent a value.
- `signals` in the tool output lists notable conditions (Bollinger breakout, MACD crossover,
  RSI extreme, golden or death cross). Mention each in one clause; an empty list means say
  nothing about them. The `indicators` block (EMA 20, MACD, Bollinger values) is for when the
  user asks about technicals.
- Do not recommend buying or selling. Describe; let the user decide.
