"""The subject axis of reader feedback.

``too_basic`` / ``too_advanced`` say the level was wrong and move depth.
``already_knew`` / ``wrong_subject`` say the level was right and the ground was
wrong: they must leave depth alone and reach the generator instead, which is
the part that can actually act on them.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from halflife import cli, mcp_server
from halflife.generation import engine
from halflife.generation.continuity import render_feedback_block
from halflife.models.base import Feedback, GenerationSource
from halflife.repository import deliveries as delivery_repo
from halflife.repository import subscriptions as subscription_repo
from halflife.shorthand import parse_shorthand
from tests.conftest import FakeClient, make_issue, make_plan

runner = CliRunner()


def _deliver(session, sub, n):
    return engine.record_issue(
        session=session,
        subscription=sub,
        issue=make_issue(n),
        source=GenerationSource.HARNESS,
    )


# ------------------------------------------------------------------ rendering


def test_no_feedback_renders_a_block_saying_so(session):
    assert render_feedback_block([]) == "Reader feedback: none so far."


def test_the_block_names_the_issue_and_translates_the_verdict():
    block = render_feedback_block([(2, "Sizing the pool", "already_knew")])
    assert "issue 2 (Sizing the pool)" in block
    assert "already knew this material" in block
    assert "override the plan" in block


# ----------------------------------------------------------------- repository


def test_only_subject_feedback_reaches_the_generator(session):
    sub = subscription_repo.create(session, parse_shorthand("x, 3, 5, 1d"))
    depth_rated = _deliver(session, sub, 1)
    subject_rated = _deliver(session, sub, 2)
    delivery_repo.set_feedback(session, depth_rated, Feedback.TOO_BASIC)
    delivery_repo.set_feedback(session, subject_rated, Feedback.WRONG_SUBJECT)

    entries = delivery_repo.recent_subject_feedback(session, sub.id)

    assert [e[0] for e in entries] == [2]


def test_subject_feedback_is_capped_and_ordered_oldest_last(session):
    sub = subscription_repo.create(session, parse_shorthand("x, 3, 5, 1d"))
    for n in range(1, 5):
        delivery_repo.set_feedback(
            session, _deliver(session, sub, n), Feedback.ALREADY_KNEW
        )

    entries = delivery_repo.recent_subject_feedback(session, sub.id, limit=3)

    assert [e[0] for e in entries] == [2, 3, 4]


# --------------------------------------------------------------------- engine


def test_the_brief_carries_recent_subject_feedback(session):
    sub = subscription_repo.create(session, parse_shorthand("x, 3, 5, 1d"))
    delivery = _deliver(session, sub, 1)
    delivery_repo.set_feedback(session, delivery, Feedback.WRONG_SUBJECT)

    brief = engine.build_brief(session=session, subscription=sub)

    assert "not what they needed" in brief.user_prompt


def test_a_fresh_series_says_there_is_no_feedback_yet(session):
    sub = subscription_repo.create(session, parse_shorthand("x, 3, 5, 1d"))
    assert "none so far" in engine.build_brief(session=session, subscription=sub).user_prompt


# ------------------------------------------------------------------------ MCP


@pytest.mark.parametrize(
    ("verdict", "axis"),
    [("too_basic", "depth"), ("already_knew", "subject"), ("wrong-subject", "subject")],
)
def test_mcp_feedback_reports_which_axis_it_moved(session, monkeypatch, verdict, axis):
    monkeypatch.setattr(mcp_server, "session_scope", lambda: _NullScope(session))
    sub = subscription_repo.create(session, parse_shorthand("x, 3, 5, 1d"))
    delivery = _deliver(session, sub, 1)

    result = json.loads(mcp_server.halflife_feedback(delivery.id, verdict))

    assert result["axis"] == axis
    assert (result["depth_now"] == result["depth_before"]) is (axis == "subject")


class _NullScope:
    """The MCP tools open their own session; hand them the test's."""

    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *exc):
        return False


# ------------------------------------------------------------------------ CLI


def test_cli_accepts_the_subject_verbs_and_leaves_depth_alone(migrated_db, monkeypatch):
    monkeypatch.setenv("COLUMNS", "200")
    client = FakeClient([make_plan(3), *[make_issue(n) for n in range(1, 6)]])
    monkeypatch.setattr(engine, "GenerationClient", lambda _settings: client)

    def run(*args):
        result = runner.invoke(cli.app, list(args))
        assert result.exit_code == 0, result.output + str(result.exception)
        return result.output

    run("subscribe", "redis eviction policies, 3, 5, 1d")
    run("run-due")
    delivery_id = run("inbox").strip().split()[0]

    output = run("feedback", delivery_id, "already-knew")

    assert "stays at 3" in output
    assert "different ground" in output
