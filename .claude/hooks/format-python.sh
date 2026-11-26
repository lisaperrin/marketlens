#!/bin/sh
# PostToolUse hook (Edit|Write): format and auto-fix any Python file Claude just touched.
# Reads the hook payload on stdin, formats with ruff, and never blocks: remaining lint errors
# are returned to Claude as additional context so it can fix them.
set -u
command -v python3 >/dev/null 2>&1 || exit 0

file=$(python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)
print((data.get("tool_input") or {}).get("file_path") or "")
')
case "$file" in
  *.py|*.pyi) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0

project="${CLAUDE_PROJECT_DIR:-$(pwd)}"
if command -v uv >/dev/null 2>&1; then
  run_ruff() { uv run --quiet --no-sync --project "$project" ruff "$@"; }
elif command -v ruff >/dev/null 2>&1; then
  run_ruff() { ruff "$@"; }
else
  exit 0
fi

run_ruff format --quiet "$file" >/dev/null 2>&1
remaining=$(run_ruff check --fix --quiet --output-format concise "$file" 2>/dev/null)
if [ -n "$remaining" ]; then
  python3 -c '
import json, sys
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
    "additionalContext": "ruff still reports issues after auto-fix:\n" + sys.argv[1]}}))
' "$remaining"
fi
exit 0
