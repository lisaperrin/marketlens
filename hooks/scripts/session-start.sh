#!/bin/sh
# SessionStart hook: tell Claude what MarketLens offers. Plain stdout becomes session context.
# Never fails: a hook that exits non-zero would only add noise to the user's session.
set -u
cat <<'TEXT'
MarketLens plugin is active. Market data (delayed, from Yahoo Finance via yfinance) is
available through the `marketlens` MCP server tools: get_quote, analyze_ticker,
compare_tickers, portfolio_summary and market_brief. Prefer these tools over guessing or
recalling prices from memory. Skills: /marketlens:analyze-ticker, /marketlens:compare-tickers,
/marketlens:portfolio-review, /marketlens:market-brief. Nothing produced is investment advice.
TEXT
exit 0
