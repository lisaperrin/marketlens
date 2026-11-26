#!/bin/sh
# UserPromptSubmit hook: when the prompt contains cashtags like $AAPL, remind Claude to use the
# live MarketLens tools. Emits JSON with additionalContext, or nothing at all.
set -u
command -v python3 >/dev/null 2>&1 || exit 0
python3 -c '
import json
import re
import sys

try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

prompt = str(payload.get("prompt", ""))
# Common shell variables that look like cashtags but are not tickers.
NOT_TICKERS = {
    "HOME", "PATH", "USER", "SHELL", "PWD", "TERM", "LANG", "EDITOR", "PS", "UID", "TMP",
    "TEMP", "TZ", "CI", "ARGS", "ARGV", "NAME", "FILE", "DIR", "ENV", "HOST", "PORT", "URL",
}
tickers = sorted({m for m in re.findall(r"\$([A-Z]{1,5})\b", prompt) if m not in NOT_TICKERS})
if not tickers:
    sys.exit(0)

symbols = ", ".join(tickers)
context = (
    f"The prompt mentions ticker symbol(s) {symbols}. Use the marketlens MCP tools for live "
    "data: get_quote for prices, analyze_ticker for return/risk/indicators, compare_tickers "
    "for several symbols. Do not quote prices from memory."
)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": context,
    }
}))
'
exit 0
