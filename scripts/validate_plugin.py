"""Check that the Claude Code plugin files in this repository are coherent.

Usage: ``uv run python scripts/validate_plugin.py [--with-claude-cli]``

Exit code 0 and ``OK`` when everything lines up; otherwise one problem per line and exit 1.
``--with-claude-cli`` additionally runs ``claude plugin validate .`` when the CLI is installed.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_NAME = "marketlens"
JSON_FILES = (
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".mcp.json",
    "hooks/hooks.json",
    ".claude/settings.json",
)


def _frontmatter(path: Path) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", path.read_text(), re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith(" "):
            fields[key.strip()] = value.strip()
    return fields


def _hook_commands(config: dict[str, object]) -> list[str]:
    commands: list[str] = []
    hooks = config.get("hooks")
    if not isinstance(hooks, dict):
        return commands
    for groups in hooks.values():
        for group in groups:
            for hook in group.get("hooks", []):
                commands.append(str(hook.get("command", "")))
    return commands


def check(root: Path) -> list[str]:
    """Return a list of problems; empty means the plugin is coherent."""
    problems: list[str] = []
    loaded: dict[str, dict[str, object]] = {}
    for relative in JSON_FILES:
        path = root / relative
        if not path.is_file():
            problems.append(f"missing {relative}")
            continue
        try:
            loaded[relative] = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            problems.append(f"{relative}: invalid JSON ({exc})")

    manifest = loaded.get(".claude-plugin/plugin.json", {})
    if manifest.get("name") != PLUGIN_NAME:
        problems.append(f"plugin.json name must be {PLUGIN_NAME!r}")
    for field in ("version", "description"):
        if not manifest.get(field):
            problems.append(f"plugin.json is missing {field!r}")

    marketplace = loaded.get(".claude-plugin/marketplace.json", {})
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        problems.append("marketplace.json must list exactly one plugin")
    else:
        entry = plugins[0]
        if entry.get("name") != manifest.get("name"):
            problems.append("marketplace plugin name does not match plugin.json")
        if entry.get("source") != "./":
            problems.append("marketplace plugin source must be './' (the repo root)")
        if entry.get("version") != manifest.get("version"):
            problems.append("marketplace plugin version does not match plugin.json")

    servers = loaded.get(".mcp.json", {}).get("mcpServers")
    if not isinstance(servers, dict) or PLUGIN_NAME not in servers:
        problems.append(f".mcp.json must define an mcpServers.{PLUGIN_NAME} entry")

    for skill_dir in sorted((root / "skills").glob("*")):
        skill = skill_dir / "SKILL.md"
        if not skill.is_file():
            problems.append(f"{skill_dir.name}: missing SKILL.md")
            continue
        fields = _frontmatter(skill)
        if fields.get("name") != skill_dir.name:
            problems.append(f"{skill}: frontmatter name must be {skill_dir.name!r}")
        if not fields.get("description"):
            problems.append(f"{skill}: frontmatter needs a description")

    for agent in sorted((root / "agents").glob("*.md")):
        fields = _frontmatter(agent)
        if fields.get("name") != agent.stem:
            problems.append(f"{agent}: frontmatter name must be {agent.stem!r}")
        if not fields.get("description"):
            problems.append(f"{agent}: frontmatter needs a description")

    for relative, variable in (
        ("hooks/hooks.json", "${CLAUDE_PLUGIN_ROOT}"),
        (".claude/settings.json", "$CLAUDE_PROJECT_DIR"),
    ):
        for command in _hook_commands(loaded.get(relative, {})):
            if variable not in command:
                problems.append(f"{relative}: hook command should use {variable}: {command}")
            script = root / command.replace(variable, "").strip('"').lstrip("/")
            if not script.is_file():
                problems.append(f"{relative}: hook script not found: {script}")
            elif not script.stat().st_mode & 0o111:
                problems.append(f"{relative}: hook script not executable: {script}")
    return problems


def main(argv: list[str]) -> int:
    """CLI entry point."""
    root = Path(__file__).resolve().parents[1]
    problems = check(root)
    if "--with-claude-cli" in argv and shutil.which("claude"):
        result = subprocess.run(
            ["claude", "plugin", "validate", str(root)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            problems.append("claude plugin validate failed:\n" + result.stdout + result.stderr)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
