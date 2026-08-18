"""Which series-plan entry an issue actually took.

The plan is advisory and the prompt explicitly permits deviation, so an issue's
position in the series is not evidence of which entry it covered. Generation
reports the entry; these tests pin down what happens when it reports honestly,
when it reports nothing, and when it reports something the plan does not have.
"""

from __future__ import annotations

import json

import pytest

from halflife import mcp_server
from halflife.generation import engine
from halflife.generation.continuity import render_plan_block
from halflife.models.base import Feedback, GenerationSource
from halflife.repository import deliveries as delivery_repo
from halflife.repository import subscriptions as subscription_repo
from halflife.shorthand import parse_shorthand
from tests.conftest import make_issue


def _plan(n=4):
    return [
        {"index": i, "title": f"Entry {i}", "focus": f"Focus {i}."} for i in range(1, n + 1)
    ]


def _subscribe(session, plan_size=4):
    sub = subscription_repo.create(session, parse_shorthand("x, 3, 5, 1d"))
    engine.ensure_series(session, sub).plan = _plan(plan_size)
    return sub


def _deliver(session, sub, n, plan_index):
    return engine.record_issue(
        session=session,
        subscription=sub,
        issue=make_issue(n, plan_index=plan_index),
        source=GenerationSource.HARNESS,
    )


# ------------------------------------------------------------------ storage


def test_a_reported_entry_is_stored(session):
    sub = _subscribe(session)
    assert _deliver(session, sub, 1, plan_index=2).plan_index == 2


@pytest.mark.parametrize("reported", [0, -1, 9])
def test_taking_no_entry_is_recorded_as_zero_not_as_unknown(session, reported):
    """0 is the honest "I went my own way", and is a fact worth keeping: null
    is reserved for rows written before the field existed, which are the only
    ones anything is allowed to guess about. A number outside the plan cannot
    be checked, so it says no more than 0 does."""
    sub = _subscribe(session)
    assert _deliver(session, sub, 1, plan_index=reported).plan_index == 0


# ------------------------------------------------------------------ queries


def test_written_entries_come_from_what_was_reported_not_from_order(session):
    sub = _subscribe(session)
    _deliver(session, sub, 1, plan_index=3)
    _deliver(session, sub, 2, plan_index=0)

    assert delivery_repo.plan_entries_written(session, sub.id) == {3}


def test_rows_predating_the_column_fall_back_to_position(session):
    """Losing the marker for legacy rows would invite covering them again,
    which is worse than the guess this column exists to remove."""
    sub = _subscribe(session)
    delivery = _deliver(session, sub, 1, plan_index=2)
    delivery.plan_index = None
    session.flush()

    assert delivery_repo.plan_entries_written(session, sub.id) == {1}


# ------------------------------------------------------------------ the block


def test_a_skipped_entry_is_not_marked_as_written(session):
    sub = _subscribe(session)
    _deliver(session, sub, 1, plan_index=2)

    prompt = engine.build_brief(session=session, subscription=sub).user_prompt

    assert "1. Entry 1 — Focus 1." in prompt
    assert "[already written]" not in prompt.split("2. Entry 2")[0]
    assert "2. Entry 2 — Focus 2. [already written]" in prompt


def test_a_rejection_marks_the_entry_taken_not_the_one_in_that_position(session):
    sub = _subscribe(session)
    delivery = _deliver(session, sub, 1, plan_index=3)
    delivery_repo.set_feedback(session, delivery, Feedback.WRONG_SUBJECT)

    prompt = engine.build_brief(session=session, subscription=sub).user_prompt

    assert "3. Entry 3 — Focus 3. [already written; the reader said" in prompt
    assert "1. Entry 1 — Focus 1.\n" in prompt


def test_a_deviation_the_reader_rejected_marks_nothing_in_the_plan(session):
    """It took no entry, so there is no entry to strike out. The prose block
    still carries the rejection."""
    sub = _subscribe(session)
    delivery = _deliver(session, sub, 1, plan_index=0)
    delivery_repo.set_feedback(session, delivery, Feedback.ALREADY_KNEW)

    prompt = engine.build_brief(session=session, subscription=sub).user_prompt

    assert "do not return to it]" not in prompt
    assert "already knew this material" in prompt


def test_the_renderer_alone_still_falls_back_to_position():
    block = render_plan_block(_plan(), "", issue_number=3)

    assert "1. Entry 1 — Focus 1. [already written]" in block
    assert "2. Entry 2 — Focus 2. [already written]" in block
    assert "3. Entry 3 — Focus 3." in block.split("[already written]")[-1]


# ------------------------------------------------------------------------ MCP


def test_mcp_record_issue_round_trips_the_reported_entry(session, monkeypatch):
    class _Scope:
        def __enter__(self):
            return session

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(mcp_server, "session_scope", _Scope)
    sub = _subscribe(session)

    result = json.loads(
        mcp_server.halflife_record_issue(
            subscription_id=sub.id,
            title="T",
            body_markdown="B",
            covered_points_added=["c"],
            open_threads=[],
            next_suggested="n",
            plan_index=2,
        )
    )

    assert result["plan_index"] == 2
