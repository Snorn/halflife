from __future__ import annotations

from datetime import timedelta

from halflife.generation import engine
from halflife.generation.prompts.depth_rubric import DEPTH_RUBRIC_VERSION
from halflife.generation.prompts.microlearning import GENERATION_PROMPT_VERSION
from halflife.models.base import Flavour, Frequency
from halflife.repository import subscriptions as subscription_repo
from halflife.shorthand import ParsedSubscription, parse_shorthand
from tests.conftest import FakeClient, make_issue, make_plan


def _subscribe(session, spec="sap web dispatcher, 3, 5, 1d"):
    return subscription_repo.create(session, parse_shorthand(spec))


def test_plan_series_stores_the_arc(session):
    sub = _subscribe(session)
    client = FakeClient([make_plan(3)])

    series = engine.plan_series(session=session, subscription=sub, client=client)

    assert series.arc_summary.startswith("Starts at the request path")
    assert [entry["index"] for entry in series.plan] == [1, 2, 3]
    assert series.plan[0]["focus"] == "Establishes thing 1."
    assert series.issue_count == 0


def test_plan_prompt_carries_topic_depth_and_flavour(session):
    sub = _subscribe(session, "terraform state, 5, 10, weekly, maintaining")
    client = FakeClient([make_plan()])

    engine.plan_series(session=session, subscription=sub, client=client)

    prompt = client.last_user_prompt
    assert "terraform state" in prompt
    assert "5 — Internals and edges" in prompt
    assert "decays first" in prompt  # the maintaining note


def test_generate_next_records_provenance(session):
    sub = _subscribe(session)
    client = FakeClient([make_plan(), make_issue(1)])
    engine.plan_series(session=session, subscription=sub, client=client)

    delivery = engine.generate_next(session=session, subscription=sub, client=client)

    assert delivery.issue_number == 1
    assert delivery.title == "Issue 1"
    assert delivery.depth == 3
    assert delivery.duration_minutes == 5
    assert delivery.model_id == "claude-opus-5"
    assert delivery.effort == "high"
    assert delivery.depth_rubric_version == DEPTH_RUBRIC_VERSION
    assert delivery.generation_prompt_version == GENERATION_PROMPT_VERSION
    assert delivery.input_tokens == 1234
    assert delivery.output_tokens == 567
    assert delivery.tenant_id == sub.tenant_id


def test_first_issue_prompt_says_the_ledger_is_empty(session):
    sub = _subscribe(session)
    client = FakeClient([make_plan(), make_issue(1)])
    engine.plan_series(session=session, subscription=sub, client=client)

    engine.generate_next(session=session, subscription=sub, client=client)

    assert "this is the first issue" in client.last_user_prompt


def test_second_issue_is_told_what_the_first_covered(session):
    """The continuity mechanism, end to end: what issue 1 established is in
    issue 2's prompt as ground it may not cover again."""
    sub = _subscribe(session)
    client = FakeClient(
        [
            make_plan(),
            make_issue(1, points=["dispatcher terminates TLS itself"], threads=["cert rotation"]),
            make_issue(2),
        ]
    )
    engine.plan_series(session=session, subscription=sub, client=client)
    engine.generate_next(session=session, subscription=sub, client=client)
    engine.generate_next(session=session, subscription=sub, client=client)

    prompt = client.last_user_prompt
    assert "dispatcher terminates TLS itself" in prompt
    assert "do NOT explain any of this again" in prompt
    assert "cert rotation" in prompt  # the open thread carried forward


def test_issue_numbers_increment_and_ledger_accumulates(session):
    sub = _subscribe(session)
    client = FakeClient([make_plan(), *[make_issue(n) for n in range(1, 4)]])
    engine.plan_series(session=session, subscription=sub, client=client)

    numbers = [
        engine.generate_next(session=session, subscription=sub, client=client).issue_number
        for _ in range(3)
    ]

    assert numbers == [1, 2, 3]
    assert sub.series.issue_count == 3
    assert [p.point for p in sub.series.coverage] == [
        "point-1a", "point-1b", "point-2a", "point-2b", "point-3a", "point-3b",
    ]
    assert [p.position for p in sub.series.coverage] == [0, 1, 2, 3, 4, 5]


def test_coverage_points_link_back_to_their_delivery(session):
    sub = _subscribe(session)
    client = FakeClient([make_plan(), make_issue(1)])
    engine.plan_series(session=session, subscription=sub, client=client)

    delivery = engine.generate_next(session=session, subscription=sub, client=client)

    assert {p.delivery_id for p in sub.series.coverage} == {delivery.id}


def test_generating_advances_the_schedule(session):
    sub = _subscribe(session, "x, 3, 5, 1d")
    before = sub.next_due_at
    client = FakeClient([make_plan(), make_issue(1)])
    engine.plan_series(session=session, subscription=sub, client=client)

    engine.generate_next(session=session, subscription=sub, client=client)

    assert sub.last_delivered_at is not None
    # Anchored to the previous slot, not to the write time — the difference is
    # the minutes a scheduled run takes, and those minutes were the creep that
    # made a fixed-time scheduler skip every other day.
    assert sub.next_due_at == before + timedelta(days=1)


def test_generation_works_without_a_plan(session):
    """--no-plan is a legitimate state: the ledger alone drives the series."""
    sub = _subscribe(session)
    client = FakeClient([make_issue(1)])

    delivery = engine.generate_next(session=session, subscription=sub, client=client)

    assert delivery.issue_number == 1
    assert sub.series.plan == []
    assert "Choose the subject yourself" in client.last_user_prompt


def test_ensure_series_is_idempotent(session):
    sub = _subscribe(session)
    first = engine.ensure_series(session, sub)
    assert engine.ensure_series(session, sub) is first


def test_word_budget_scales_with_duration():
    assert engine.word_budget(5) == 1000
    assert engine.word_budget(10) == 2000


def test_depth_appears_in_the_generation_prompt_by_name(session):
    sub = subscription_repo.create(
        session,
        ParsedSubscription(
            topic="kubernetes admission controllers",
            depth=5,
            duration_minutes=5,
            frequency=Frequency.DAILY,
            flavour=Flavour.LEARNING,
        ),
    )
    client = FakeClient([make_plan(), make_issue(1)])
    engine.plan_series(session=session, subscription=sub, client=client)
    engine.generate_next(session=session, subscription=sub, client=client)

    assert "Depth: 5 — Internals and edges" in client.last_user_prompt
    # The rubric itself rides on the system prompt, not the user prompt.
    assert "Depth rubric" in client.calls[-1]["system"]


def test_a_complete_series_refuses_to_brief(session):
    """Every route to a new issue goes through build_brief, so the cap is
    checked there rather than in the three callers."""
    import pytest
    from halflife.models.base import GenerationSource
    from halflife.repository import subscriptions as subscription_repo

    from halflife.models.base import issue_cap

    sub = _subscribe(session, "x, 1, 5, 1d")
    last = None
    for n in range(1, issue_cap(1) + 1):
        last = engine.record_issue(session=session, subscription=sub, issue=make_issue(n),
                                   source=GenerationSource.HARNESS)

    with pytest.raises(engine.SeriesComplete, match="depth 2"):
        engine.build_brief(session=session, subscription=sub)

    subscription_repo.apply_feedback_to_depth(
        session, sub,
        __import__("halflife.models.base", fromlist=["Feedback"]).Feedback.TOO_BASIC,
        rated=last,
    )
    assert engine.build_brief(session=session, subscription=sub).issue_number == issue_cap(1) + 1
