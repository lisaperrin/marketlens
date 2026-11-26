#!/bin/sh
# PreToolUse hook (Bash): refuse git commands that rewrite shared history or skip checks.
# Exit 2 blocks the call and sends stderr to Claude as the reason. Exit 0 lets it through.
set -u
command -v python3 >/dev/null 2>&1 || exit 0
python3 -c '
import json
import re
import shlex
import sys

try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

command = str((payload.get("tool_input") or {}).get("command") or "")
if not command:
    sys.exit(0)

# Split into simple commands first (newlines and shell operators), then tokenise each.
GLOBAL_FLAGS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
PREFIXES = {"command", "exec", "sudo", "env", "nice", "time"}


def tokens_of(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def git_args(tokens: list[str]) -> list[str] | None:
    """Return the arguments after `git` (global options stripped) if this runs git."""
    i = 0
    while i < len(tokens) and (tokens[i] in PREFIXES or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i])):
        i += 1
    if i >= len(tokens) or tokens[i].rsplit("/", 1)[-1] != "git":
        return None
    args = tokens[i + 1 :]
    while args and args[0].startswith("-"):
        flag = args.pop(0)
        if flag in GLOBAL_FLAGS_WITH_VALUE and args:
            args.pop(0)
    return args


TAKES_VALUE = {"-m", "--message", "-F", "--file", "-C", "--reuse-message", "-c", "--reedit-message",
               "--author", "--date", "-o", "--push-option", "--receive-pack", "--repo"}


def flags_of(rest: list[str]) -> list[str]:
    """Option tokens only, skipping the values of options that take one (so -m "-n" is text)."""
    flags: list[str] = []
    skip = False
    for token in rest:
        if skip:
            skip = False
            continue
        if token in TAKES_VALUE:
            skip = True
            continue
        if token.startswith("-"):
            flags.append(token)
    return flags


def verdict(args: list[str]) -> str | None:
    if not args:
        return None
    sub, rest = args[0], args[1:]
    flags = flags_of(rest)
    if sub == "push":
        if any(f == "--force-with-lease" or f.startswith("--force-with-lease=") for f in flags):
            return None
        if "--force" in flags or "-f" in flags or any(a.startswith("+") for a in rest):
            return "force-push rewrites shared history; use --force-with-lease on a feature branch"
    if sub == "commit":
        if "--no-verify" in flags or "-n" in flags:
            return "--no-verify skips the project checks; run them instead"
    if sub == "reset" and "--hard" in flags:
        return "git reset --hard discards uncommitted work; stash or commit first"
    return None


for segment in re.split(r"\n|;|&&|\|\||\|", command):
    args = git_args(tokens_of(segment))
    if args is None:
        continue
    reason = verdict(args)
    if reason:
        print(f"guard-git: blocked `{segment.strip()}`: {reason}", file=sys.stderr)
        sys.exit(2)
sys.exit(0)
'
