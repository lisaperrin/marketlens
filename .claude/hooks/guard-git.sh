#!/bin/sh
# PreToolUse hook (Bash): refuse git commands that rewrite shared history or skip checks.
# Exit 2 blocks the call and sends stderr to Claude as the reason. Exit 0 lets it through.
set -u
command -v python3 >/dev/null 2>&1 || exit 0
MARKETLENS_HOOK_PAYLOAD=$(cat)
export MARKETLENS_HOOK_PAYLOAD
python3 - <<'PY'
import json
import os
import shlex
import sys

try:
    payload = json.loads(os.environ.get("MARKETLENS_HOOK_PAYLOAD") or "{}")
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

command = str((payload.get("tool_input") or {}).get("command") or "")
if not command:
    sys.exit(0)

try:
    tokens = shlex.split(command)
except ValueError:
    tokens = command.split()

SEPARATORS = {"&&", "||", ";", "|", "&"}
segments: list[list[str]] = [[]]
for token in tokens:
    if token in SEPARATORS:
        segments.append([])
    else:
        segments[-1].append(token)


def verdict(segment: list[str]) -> str | None:
    if "git" not in segment:
        return None
    args = segment[segment.index("git") + 1 :]
    if not args:
        return None
    sub = args[0]
    if sub == "push":
        if "--force-with-lease" in args:
            return None
        if "--force" in args or "-f" in args or any(a.startswith("+") for a in args[1:]):
            return "force-push rewrites shared history; use --force-with-lease on a feature branch"
    if sub == "commit" and ("--no-verify" in args or "-n" in args):
        return "--no-verify skips the project's checks; run them instead"
    if sub == "reset" and "--hard" in args:
        return "git reset --hard discards uncommitted work; stash or commit first"
    return None


for seg in segments:
    reason = verdict(seg)
    if reason:
        print(f"guard-git: blocked `{' '.join(seg)}`: {reason}", file=sys.stderr)
        sys.exit(2)
sys.exit(0)
PY
