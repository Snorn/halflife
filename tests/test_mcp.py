"""The MCP surface — step 2's in-harness generation path.

These exercise the brief/record seam that lets a harness generate without an
API key. Nothing here touches the network; the "model" is the test writing an
issue by hand, which is exactly what the harness does at runtime.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from halflife import mcp_server
from halflife.generation import engine
from halflife.generation.schemas import GeneratedIssue, PlannedIssue
from halflife.models.base import GenerationSource
from halflife.repository import subscriptions as subscription_repo
from halflife.shorthand import parse_shorthand
from tests.conftest import FakeClient, make_issue


def _json(raw: str):
    return json.loads(raw)


def _issue(n: int = 1) -> GeneratedIssue:
    return GeneratedIssue(
        title=f"Issue {n}",
        body_markdown=f"Body {n}.",
        covered_points_added=[f"claim {n}a", f"claim {n}b"],
        open_threads=[],
        next_suggested="next",
    )


# --------------------------------------------------------------- engine seam


def test_brief_carries_the_prompts_without_generating(session):
    sub = subscription_repo.create(session, parse_shorthand("sap web dispatcher, 4, 5, 1d"))

    brief = engine.build_brief(session=session, subscription=sub)

    assert brief.issue_number == 1
    assert brief.word_budget == 1000
    assert "Depth rubric" in brief.system_prompt
    assert "Depth: 4 — Non-obvious" in brief.user_prompt
    assert "sap web dispatcher" in brief.user_prompt
    # Nothing was written by merely asking for a brief.
    assert sub.series.issue_count == 0


def test_brief_then_record_is_equivalent_to_generating(session):
    sub = subscription_repo.create(session, parse_shorthand("kubernetes, 3, 5, 1d"))
    engine.build_brief(session=session, subscription=sub)

    delivery = engine.record_issue(
        session=session,
        subscription=sub,
        issue=_issue(1),
        source=GenerationSource.HARNESS,
    )

    assert delivery.issue_number == 1
    assert sub.series.issue_count == 1
    assert [p.point for p in sub.series.coverage] == ["claim 1a", "claim 1b"]
    assert sub.last_delivered_at is not None


def test_harness_issues_record_an_honest_unknown_model(session):
    sub = subscription_repo.create(session, parse_shorthand("kubernetes, 3, 5, 1d"))

    delivery = engine.record_issue(
        session=session, subscription=sub, issue=_issue(), source=GenerationSource.HARNESS
    )

    assert delivery.source is GenerationSource.HARNESS
    assert delivery.model_id is None
    assert delivery.effort is None
    # Prompt provenance is still recorded — that part is knowable either way.
    assert delivery.depth_rubric_version
    assert delivery.generation_prompt_version


def test_api_path_still_records_itself_as_api(session):
    sub = subscription_repo.create(session, parse_shorthand("kubernetes, 3, 5, 1d"))

    delivery = engine.generate_next(
        session=session, subscription=sub, client=FakeClient([make_issue(1)])
    )

    assert delivery.source is GenerationSource.API
    assert delivery.model_id == "claude-opus-5"
    assert delivery.effort == "high"


def test_second_brief_contains_what_the_first_issue_established(session):
    """The continuity mechanism survives the inversion."""
    sub = subscription_repo.create(session, parse_shorthand("kubernetes, 4, 5, 1d"))
    engine.record_issue(
        session=session,
        subscription=sub,
        issue=GeneratedIssue(
            title="One",
            body_markdown="b",
            covered_points_added=["admission runs before persistence"],
            open_threads=["webhook ordering"],
            next_suggested="n",
        ),
        source=GenerationSource.HARNESS,
    )

    brief = engine.build_brief(session=session, subscription=sub)

    assert brief.issue_number == 2
    assert "admission runs before persistence" in brief.user_prompt
    assert "do NOT explain any of this again" in brief.user_prompt
    assert "webhook ordering" in brief.user_prompt


# --------------------------------------------------------------- MCP tools


def test_tools_are_registered_and_dispatchable(migrated_db):
    """Goes through real MCP dispatch, not just the Python function."""
    tools = asyncio.run(mcp_server.server.list_tools())
    names = {t.name for t in tools}

    assert {
        "halflife_list_due",
        "halflife_plan_brief",
        "halflife_record_plan",
        "halflife_next_brief",
        "halflife_record_issue",
        "halflife_compaction_brief",
        "halflife_record_compaction",
        "halflife_pending_reads",
        "halflife_read",
        "halflife_feedback",
    } <= names

    result = asyncio.run(mcp_server.server.call_tool("halflife_list_due", {}))
    assert result.is_error is False


def test_full_harness_loop_through_the_tools(migrated_db):
    created = _json(mcp_server.halflife_subscribe("sap web dispatcher, 4, 5, 1d"))
    sub_id = created["subscription_id"]

    due = _json(mcp_server.halflife_list_due())
    assert [d["topic"] for d in due] == ["sap web dispatcher"]

    brief = _json(mcp_server.halflife_next_brief(sub_id))
    assert brief["depth"] == 4
    assert brief["issue_number"] == 1
    assert brief["needs_compaction"] is False
    assert "Depth rubric" in brief["system_prompt"]

    recorded = _json(
        mcp_server.halflife_record_issue(
            subscription_id=sub_id,
            title="Sizing the dispatcher",
            body_markdown="The body.",
            covered_points_added=["MPI buffers are counted, not sized in bytes"],
            open_threads=[],
            next_suggested="failure detection",
            model_id="claude-opus-5",
        )
    )
    assert recorded["issue_number"] == 1

    pending = _json(mcp_server.halflife_pending_reads())
    assert pending[0]["title"] == "Sizing the dispatcher"

    read = _json(mcp_server.halflife_read(pending[0]["delivery_id"]))
    assert read["body_markdown"] == "The body."

    # Reading marks it read.
    assert _json(mcp_server.halflife_pending_reads()) == []

    verdict = _json(mcp_server.halflife_feedback(read["delivery_id"], "too-advanced"))
    assert verdict["depth_before"] == 4
    assert verdict["depth_now"] == 3

    # The next brief reflects both the new depth and the ledger.
    nxt = _json(mcp_server.halflife_next_brief(sub_id))
    assert nxt["depth"] == 3
    assert "MPI buffers are counted" in nxt["user_prompt"]


def test_a_new_subscription_starts_unplanned_and_says_so(migrated_db):
    sub_id = _json(mcp_server.halflife_subscribe("kubernetes, 4, 5, 1d"))["subscription_id"]

    brief = _json(mcp_server.halflife_plan_brief(sub_id))

    assert brief["already_planned"] is False
    assert brief["issue_count_to_plan"] == 10
    assert "kubernetes" in brief["user_prompt"]
    assert "Depth rubric" in brief["system_prompt"]


def test_planning_through_the_tools_reaches_the_issue_brief(migrated_db):
    """The plan is only useful if it turns up in the next issue's prompt."""
    sub_id = _json(mcp_server.halflife_subscribe("kubernetes, 4, 5, 1d"))["subscription_id"]

    out = _json(
        mcp_server.halflife_record_plan(
            subscription_id=sub_id,
            arc_summary="Starts at the request path, ends at failure modes.",
            issues=[
                PlannedIssue(index=1, title="The admission chain", focus="Establishes ordering."),
                PlannedIssue(index=2, title="Failure policy", focus="Establishes blast radius."),
            ],
        )
    )
    assert out["planned_issues"] == 2

    brief = _json(mcp_server.halflife_next_brief(sub_id))
    assert "The admission chain" in brief["user_prompt"]
    assert "Establishes ordering." in brief["user_prompt"]
    assert "Starts at the request path" in brief["user_prompt"]

    # And the brief no longer reports the series as unplanned.
    assert _json(mcp_server.halflife_plan_brief(sub_id))["already_planned"] is True


def test_recording_a_plan_replaces_the_previous_one(migrated_db):
    sub_id = _json(mcp_server.halflife_subscribe("kubernetes, 4, 5, 1d"))["subscription_id"]
    mcp_server.halflife_record_plan(
        subscription_id=sub_id,
        arc_summary="First attempt.",
        issues=[PlannedIssue(index=1, title="Old", focus="Old focus.")],
    )

    mcp_server.halflife_record_plan(
        subscription_id=sub_id,
        arc_summary="Second attempt.",
        issues=[PlannedIssue(index=1, title="New", focus="New focus.")],
    )

    brief = _json(mcp_server.halflife_next_brief(sub_id))
    assert "New" in brief["user_prompt"]
    assert "Old" not in brief["user_prompt"]


def test_empty_plan_is_rejected(migrated_db):
    sub_id = _json(mcp_server.halflife_subscribe("kubernetes, 4, 5, 1d"))["subscription_id"]

    out = _json(mcp_server.halflife_record_plan(sub_id, "An arc.", []))

    assert "error" in out


def test_reported_model_is_kept_when_the_harness_supplies_it(migrated_db):
    sub_id = _json(mcp_server.halflife_subscribe("kubernetes, 3, 5, 1d"))["subscription_id"]
    mcp_server.halflife_record_issue(
        subscription_id=sub_id,
        title="T",
        body_markdown="B",
        covered_points_added=["c"],
        open_threads=[],
        next_suggested="n",
        model_id="claude-sonnet-5",
    )
    delivery_id = _json(mcp_server.halflife_pending_reads())[0]["delivery_id"]
    read = _json(mcp_server.halflife_read(delivery_id))
    assert read["delivery_id"] == delivery_id


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        (mcp_server.halflife_next_brief, ("nonexistent",)),
        (mcp_server.halflife_compaction_brief, ("nonexistent",)),
        (mcp_server.halflife_read, ("nonexistent",)),
    ],
)
def test_unknown_ids_return_an_error_rather_than_raising(migrated_db, tool, args):
    assert "error" in _json(tool(*args))


def test_bad_feedback_verdict_is_rejected_with_the_options(migrated_db):
    sub_id = _json(mcp_server.halflife_subscribe("kubernetes, 3, 5, 1d"))["subscription_id"]
    mcp_server.halflife_record_issue(
        subscription_id=sub_id,
        title="T",
        body_markdown="B",
        covered_points_added=["c"],
        open_threads=[],
        next_suggested="n",
    )
    delivery_id = _json(mcp_server.halflife_pending_reads())[0]["delivery_id"]

    out = _json(mcp_server.halflife_feedback(delivery_id, "meh"))

    assert "too_basic" in out["error"]


def test_bad_shorthand_is_rejected(migrated_db):
    assert "error" in _json(mcp_server.halflife_subscribe("topic, 9, 5, 1d"))


def test_compaction_brief_is_empty_until_the_ledger_is_large(migrated_db):
    sub_id = _json(mcp_server.halflife_subscribe("kubernetes, 3, 5, 1d"))["subscription_id"]
    assert _json(mcp_server.halflife_compaction_brief(sub_id)) == {"nothing_to_compact": True}


def test_compaction_round_trip_through_the_tools(session, migrated_db):
    from halflife.generation.continuity import COMPACT_TRIGGER

    sub_id = _json(mcp_server.halflife_subscribe("kubernetes, 4, 5, 1d"))["subscription_id"]
    mcp_server.halflife_record_issue(
        subscription_id=sub_id,
        title="Seed",
        body_markdown="B",
        covered_points_added=[f"established fact {i}" for i in range(COMPACT_TRIGGER)],
        open_threads=[],
        next_suggested="n",
    )

    assert _json(mcp_server.halflife_next_brief(sub_id))["needs_compaction"] is True

    brief = _json(mcp_server.halflife_compaction_brief(sub_id))
    assert brief["entry_count"] == 80
    assert brief["target"] == 20
    assert "established fact 0" in brief["user_prompt"]

    out = _json(
        mcp_server.halflife_record_compaction(sub_id, [f"merged {i}" for i in range(20)])
    )
    assert out["summaries_written"] == 20
    assert out["active_ledger_size"] == COMPACT_TRIGGER - 80 + 20

    after = _json(mcp_server.halflife_next_brief(sub_id))
    assert "merged 0" in after["user_prompt"]
    assert "established fact 0" not in after["user_prompt"]
