"""The repo root is a Claude Code plugin; keep its manifest, skills, agents and hooks coherent."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "marketlens"
EXPECTED_SKILLS = {
    "analyze-ticker",
    "compare-tickers",
    "portfolio-review",
    "market-brief",
    "add-indicator",
}
EXPECTED_AGENTS = {"market-analyst", "quant-reviewer"}
EXPECTED_MCP_TOOLS = {
    "get_quote",
    "analyze_ticker",
    "compare_tickers",
    "portfolio_summary",
    "market_brief",
}


def load_json(relative: str) -> dict:  # type: ignore[type-arg]
    data = json.loads((ROOT / relative).read_text())
    assert isinstance(data, dict)
    return data


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{path} has no YAML frontmatter"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def test_manifest_has_required_fields() -> None:
    manifest = load_json(".claude-plugin/plugin.json")
    assert manifest["name"] == PLUGIN_NAME
    assert manifest["version"] == "0.1.0"
    assert manifest["description"]
    assert manifest["author"]["name"]
    assert manifest["license"] == "MIT"


def test_marketplace_points_at_repo_root_plugin() -> None:
    marketplace = load_json(".claude-plugin/marketplace.json")
    assert marketplace["name"]
    assert marketplace["owner"]["name"]
    (plugin,) = marketplace["plugins"]
    assert plugin["name"] == PLUGIN_NAME
    assert plugin["source"] == "./"


def test_mcp_config_launches_the_server_via_uvx() -> None:
    config = load_json(".mcp.json")
    server = config["mcpServers"][PLUGIN_NAME]
    assert server["command"] == "uvx"
    assert "marketlens-mcp" in server["args"]


def test_skills_exist_with_frontmatter() -> None:
    found = {p.parent.name for p in ROOT.glob("skills/*/SKILL.md")}
    assert found == EXPECTED_SKILLS
    for path in ROOT.glob("skills/*/SKILL.md"):
        fields = frontmatter(path)
        assert fields["name"] == path.parent.name
        assert len(fields["description"]) > 20
        assert path.read_text().count("\n") > 10, f"{path} is too thin"


def test_user_facing_skills_reference_mcp_tools_or_cli() -> None:
    for skill in EXPECTED_SKILLS - {"add-indicator"}:
        text = (ROOT / "skills" / skill / "SKILL.md").read_text()
        assert "marketlens" in text
        assert any(tool in text for tool in EXPECTED_MCP_TOOLS), skill


def test_agents_exist_with_frontmatter() -> None:
    found = {p.stem for p in ROOT.glob("agents/*.md")}
    assert found == EXPECTED_AGENTS
    for path in ROOT.glob("agents/*.md"):
        fields = frontmatter(path)
        assert fields["name"] == path.stem
        assert len(fields["description"]) > 20
        assert "tools" in fields


def test_plugin_hooks_cover_session_start_and_prompt_submit() -> None:
    hooks = load_json("hooks/hooks.json")["hooks"]
    assert set(hooks) == {"SessionStart", "UserPromptSubmit"}
    for groups in hooks.values():
        for group in groups:
            for hook in group["hooks"]:
                assert hook["type"] == "command"
                assert "${CLAUDE_PLUGIN_ROOT}" in hook["command"]
                script = hook["command"].replace("${CLAUDE_PLUGIN_ROOT}", str(ROOT)).strip('"')
                assert Path(script).is_file(), script


def test_project_settings_wire_format_and_guard_hooks() -> None:
    settings = load_json(".claude/settings.json")
    hooks = settings["hooks"]
    post = hooks["PostToolUse"][0]
    assert post["matcher"] == "Edit|Write"
    assert "format-python.sh" in post["hooks"][0]["command"]
    pre = hooks["PreToolUse"][0]
    assert pre["matcher"] == "Bash"
    assert "guard-git.sh" in pre["hooks"][0]["command"]
    assert any(rule.startswith("Bash(uv run pytest") for rule in settings["permissions"]["allow"])
    assert "Read(./.env)" in settings["permissions"]["deny"]


@pytest.mark.parametrize(
    "script",
    [
        ".claude/hooks/format-python.sh",
        ".claude/hooks/guard-git.sh",
        "hooks/scripts/session-start.sh",
        "hooks/scripts/ticker-hint.sh",
    ],
)
def test_hook_scripts_are_executable_posix_sh(script: str) -> None:
    path = ROOT / script
    assert path.is_file()
    assert path.stat().st_mode & 0o111, f"{script} is not executable"
    assert path.read_text().startswith("#!/bin/sh\n")


def test_validate_plugin_script_passes() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_plugin", ROOT / "scripts/validate_plugin.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.check(ROOT) == []
