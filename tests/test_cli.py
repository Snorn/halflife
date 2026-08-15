"""End-to-end through the CLI with generation stubbed out.

This is the wiring test: repositories, engine, session handling and rendering
all have to actually fit together. It does not touch the network.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from halflife import cli
from halflife.generation import engine
from tests.conftest import FakeClient, make_issue, make_plan

runner = CliRunner()


@pytest.fixture(autouse=True)
def wide_terminal(monkeypatch):
    """CliRunner reports an 80-column terminal, which wraps the `ls` table."""
    monkeypatch.setenv("COLUMNS", "200")


@pytest.fixture
def fake_generation(monkeypatch):
    """Make every GenerationClient the engine constructs return canned output."""
    client = FakeClient([make_plan(3), *[make_issue(n) for n in range(1, 6)]])
    monkeypatch.setattr(engine, "GenerationClient", lambda _settings: client)
    return client


def _run(*args) -> str:
    result = runner.invoke(cli.app, list(args))
    assert result.exit_code == 0, result.output + str(result.exception)
    return result.output


def test_subscribe_list_generate_read_feedback(migrated_db, fake_generation):
    output = _run("subscribe", "sap web dispatcher, 3, 5, 1d")
    assert "Subscribed" in output
    assert "Planned issue 1" in output  # the arc came back

    assert "sap web dispatcher" in _run("ls")

    # Generate the first issue for whatever is due.
    assert "Issue 1" in _run("run-due")
    assert "Issue 1" in _run("inbox")
    assert "Body of issue 1." in _run("read", "latest")

    # Reading marks it read, so the inbox empties.
    assert "Nothing unread" in _run("inbox")


def test_feedback_moves_the_subscriptions_depth(migrated_db, fake_generation):
    _run("subscribe", "postgres connection pooling, 3, 5, 1d")
    _run("run-due")

    inbox = _run("inbox")
    delivery_id = inbox.strip().split()[0]

    output = _run("feedback", delivery_id, "too-basic")
    assert "Depth 3 -> 4" in output

    assert " 4 " in _run("ls")


def test_feedback_at_the_ceiling_says_depth_is_unchanged(migrated_db, fake_generation):
    _run("subscribe", "tls certificate chains, 5, 5, 1d")
    _run("run-due")
    delivery_id = _run("inbox").strip().split()[0]

    assert "stays at 5" in _run("feedback", delivery_id, "too-basic")


def test_run_due_is_idempotent_within_the_interval(migrated_db, fake_generation):
    _run("subscribe", "kubernetes, 3, 5, 1d")
    assert "Issue 1" in _run("run-due")
    # The schedule advanced by a day, so a second run has nothing to do.
    assert "Nothing due" in _run("run-due")


def test_dry_run_does_not_generate(migrated_db, fake_generation):
    _run("subscribe", "kubernetes, 3, 5, 1d")
    calls_before = len(fake_generation.calls)

    output = _run("run-due", "--dry-run")

    assert "kubernetes" in output
    assert len(fake_generation.calls) == calls_before
    # Still due, because nothing was generated.
    assert "Issue 1" in _run("run-due")


def test_series_command_shows_plan_ledger_and_threads(migrated_db, fake_generation):
    _run("subscribe", "terraform state, 4, 5, 1d")
    _run("run-due")

    listing = _run("ls")
    sub_prefix = listing.strip().splitlines()[1].split()[0]

    output = _run("series", sub_prefix)
    assert "Plan" in output
    assert "Coverage ledger" in output
    assert "point-1a" in output
    assert "Open threads" in output


def test_pause_stops_a_subscription_coming_due(migrated_db, fake_generation):
    _run("subscribe", "kubernetes, 3, 5, 1d")
    sub_prefix = _run("ls").strip().splitlines()[1].split()[0]

    _run("pause", sub_prefix)
    assert "Nothing due" in _run("run-due")

    _run("resume", sub_prefix)
    assert "Issue 1" in _run("run-due")


def test_bad_shorthand_exits_nonzero_with_a_usable_message(migrated_db):
    result = runner.invoke(cli.app, ["subscribe", "x, 9, 5, 1d"])
    assert result.exit_code == 1
    assert "Depth must be between 1 and 5" in result.output


def test_no_plan_skips_the_arc_call(migrated_db, monkeypatch):
    client = FakeClient([])  # any call would raise
    monkeypatch.setattr(engine, "GenerationClient", lambda _settings: client)

    output = _run("subscribe", "kubernetes, 3, 5, 1d", "--no-plan")

    assert "Subscribed" in output
    assert client.calls == []
