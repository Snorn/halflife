"""The built-in guide.

Its whole value is being accurate, so these check it stays in step with the
surfaces it documents rather than checking its prose.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from typer.testing import CliRunner

from halflife import cli, guide, mcp_server

runner = CliRunner()


def _cli_command_names() -> set[str]:
    """Typer leaves `name` unset when it is derived from the function name."""
    return {
        info.name or info.callback.__name__.replace("_", "-")
        for info in cli.app.registered_commands
    }


def test_cli_help_command_renders(migrated_db):
    result = runner.invoke(cli.app, ["help"])

    assert result.exit_code == 0
    assert "HalfLife" in result.output
    assert "The loop" in result.output


def test_cli_help_needs_no_database(tmp_path, monkeypatch):
    """Someone reaching for help may not have run init yet."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HALFLIFE_DB_URL", f"sqlite+pysqlite:///{tmp_path}/absent.db")

    assert runner.invoke(cli.app, ["help"]).exit_code == 0


def test_mcp_help_tool_returns_the_same_text(migrated_db):
    assert mcp_server.halflife_help() == guide.guide_text()


def test_help_is_advertised_over_mcp(migrated_db):
    names = {t.name for t in asyncio.run(mcp_server.server.list_tools())}
    assert "halflife_help" in names


def test_guide_lists_every_mcp_tool(migrated_db):
    """A tool the guide omits is a tool nobody discovers."""
    advertised = {t.name for t in asyncio.run(mcp_server.server.list_tools())}
    text = guide.guide_text()

    missing = sorted(name for name in advertised if name not in text)

    assert not missing, f"guide does not mention: {missing}"


def test_guide_lists_every_cli_command(migrated_db):
    """And a command it omits is one nobody finds either."""
    text = guide.guide_text()

    # generate is API-only and covered by the closing section rather than the
    # command table; run-due is named there explicitly.
    missing = sorted(
        name for name in _cli_command_names() if name not in text and name != "generate"
    )

    assert not missing, f"guide does not mention: {missing}"


def test_guide_mentions_no_command_that_does_not_exist(migrated_db):
    """Stops the guide drifting ahead of the CLI."""
    commands = _cli_command_names()
    claimed = set(re.findall(r"`halflife ([a-z-]+)", guide.guide_text()))

    assert claimed <= commands, f"guide invents: {sorted(claimed - commands)}"


def test_readme_lists_every_mcp_tool(migrated_db):
    """The README drifted behind the tool surface once; this is why it stopped.

    Tool names are unique enough to check by substring, and a tool missing from
    the README is one a reader has no way to know exists.
    """
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    advertised = {t.name for t in asyncio.run(mcp_server.server.list_tools())}

    missing = sorted(name for name in advertised if name not in readme)

    assert not missing, f"README does not mention: {missing}"


def test_guide_covers_all_five_depths():
    text = guide.guide_text()
    for depth in range(1, 6):
        assert f"| {depth} |" in text
