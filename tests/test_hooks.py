"""Run the hook shell scripts the way Claude Code does: JSON on stdin, exit code as verdict."""

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_hook(
    script: str, payload: dict, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:  # type: ignore[type-arg]
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT), "CLAUDE_PLUGIN_ROOT": str(ROOT)}
    return subprocess.run(
        [str(ROOT / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=cwd or ROOT,
        env=env,
        timeout=120,
        check=False,
    )


# -- .claude/hooks/format-python.sh ----------------------------------------------------------


def test_format_hook_reformats_the_edited_python_file(tmp_path: Path) -> None:
    target = tmp_path / "messy.py"
    target.write_text("import sys,os\nx=[1,2,\n3]\nprint(os.name,sys.argv,x)\n")
    result = run_hook(".claude/hooks/format-python.sh", {"tool_input": {"file_path": str(target)}})
    assert result.returncode == 0, result.stderr
    formatted = target.read_text()
    assert "x = [1, 2, 3]" in formatted
    assert formatted.startswith("import os\nimport sys\n")


def test_format_hook_ignores_non_python_files(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    target.write_text("# hi\n")
    result = run_hook(".claude/hooks/format-python.sh", {"tool_input": {"file_path": str(target)}})
    assert result.returncode == 0
    assert target.read_text() == "# hi\n"


def test_format_hook_exits_zero_without_file_path() -> None:
    result = run_hook(
        ".claude/hooks/format-python.sh", {"tool_input": {"notebook_path": "x.ipynb"}}
    )
    assert result.returncode == 0
    assert result.stdout == ""


# -- .claude/hooks/guard-git.sh -------------------------------------------------------------


def run_guard(command: str) -> subprocess.CompletedProcess[str]:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    return run_hook(".claude/hooks/guard-git.sh", payload)


@pytest.mark.parametrize(
    "command",
    [
        "git push --force origin main",
        "git push -f origin main",
        "git push origin +main",
        "git commit -m x --no-verify",
        "git reset --hard HEAD~3",
    ],
)
def test_guard_blocks_destructive_git(command: str) -> None:
    result = run_hook(
        ".claude/hooks/guard-git.sh", {"tool_name": "Bash", "tool_input": {"command": command}}
    )
    assert result.returncode == 2
    assert result.stderr.strip()


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git push -u origin feature/x",
        "git push --force-with-lease origin feature/x",
        "uv run pytest -q",
        "echo 'git push --force' > notes.txt",
    ],
)
def test_guard_allows_ordinary_commands(command: str) -> None:
    result = run_hook(
        ".claude/hooks/guard-git.sh", {"tool_name": "Bash", "tool_input": {"command": command}}
    )
    assert result.returncode == 0, result.stderr


def test_guard_exits_zero_on_empty_input() -> None:
    result = run_hook(".claude/hooks/guard-git.sh", {})
    assert result.returncode == 0


# -- hooks/scripts/ticker-hint.sh ----------------------------------------------------------


def test_ticker_hint_adds_context_for_cashtags() -> None:
    result = run_hook(
        "hooks/scripts/ticker-hint.sh", {"prompt": "how is $AAPL doing vs $MSFT today?"}
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "AAPL" in context and "MSFT" in context
    assert "get_quote" in context or "analyze_ticker" in context


def test_ticker_hint_is_silent_without_cashtags() -> None:
    result = run_hook("hooks/scripts/ticker-hint.sh", {"prompt": "refactor the cache module"})
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_ticker_hint_ignores_shell_style_variables() -> None:
    result = run_hook("hooks/scripts/ticker-hint.sh", {"prompt": "echo $HOME and $PATH"})
    assert result.returncode == 0
    # HOME and PATH look like cashtags; the hook must not treat common env vars as tickers.
    assert "HOME" not in result.stdout


# -- hooks/scripts/session-start.sh -----------------------------------------------------------


def test_session_start_prints_plugin_context(tmp_path: Path) -> None:
    result = run_hook(
        "hooks/scripts/session-start.sh", {"hook_event_name": "SessionStart", "source": "startup"}
    )
    assert result.returncode == 0
    assert "MarketLens" in result.stdout
    assert "analyze_ticker" in result.stdout
