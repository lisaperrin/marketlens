---
name: compare-tickers
description: Compare two or more stocks or ETFs side by side on return, risk, valuation and correlation. Use when the user weighs alternatives, asks "X or Y", or wants to know how diversified a set of holdings is.
argument-hint: <SYMBOL> <SYMBOL> [...] [--period 1y]
allowed-tools: mcp__plugin_marketlens_marketlens__compare_tickers Bash(uv run marketlens *)
---

# Compare tickers

Compare the symbols in `$ARGUMENTS` with live data and explain what separates them.

## Steps

1. **Parse the arguments.** Everything that looks like a ticker is a symbol; a trailing
   `--period <p>` sets the history window (default `1y`). Fewer than two symbols: ask for
   another one and stop.
2. **Fetch the comparison.** Call the `compare_tickers` MCP tool with the symbol list and
   period. Fallback: `uv run marketlens --json compare <symbols> --period <p>`.
3. **Build the table** from the tool output, one row per symbol:

   | Symbol | Price | Return | Volatility | Max drawdown | Sharpe | RSI 14 | P/E |

   Convert fractions to percentages with one decimal. Use "n/a" where the value is `None`.
4. **Read the correlation matrix.** Call out any pair above 0.8 (they move together, little
   diversification between them) and any pair below 0.3 (genuinely different exposures).
5. **Write the verdict** in three short paragraphs:
   - Which symbol delivered the most return per unit of risk (highest Sharpe) and which
     carried the deepest drawdown.
   - Valuation differences and whether they are explained by growth or sector.
   - What the correlation means for holding several of them at once.
6. End with: "Delayed data, not investment advice."

## Benchmark (only when asked)

If the user wants the comparison "relative to the market" or names an index, pass
`benchmark="<SYMBOL>"`; the table then gains `Excess` (return minus benchmark) and `Beta`
columns. Leave it out otherwise.

## Rules

- Keep the comparison to the data returned. If the user asks "which should I buy", explain
  the trade-offs and decline to pick for them.
- Mention the period explicitly; a 1-month comparison and a 5-year one can tell opposite
  stories.
