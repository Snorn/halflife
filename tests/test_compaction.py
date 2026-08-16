"""Ledger compaction.

The ledger grows at roughly thirteen points an issue, so a daily subscription
outgrows a promptable ledger in about a fortnight. Compaction folds the oldest
slice into fewer, denser claims rather than dropping it — the property that
matters is that nothing is ever deleted and ordering survives.
"""

from __future__ import annotations

from halflife.generation import continuity, engine
from halflife.generation.continuity import COMPACT_OLDEST, COMPACT_TRIGGER
from halflife.generation.schemas import CompactedLedger
from halflife.models.base import CoverageKind
from halflife.repository import subscriptions as subscription_repo
from halflife.shorthand import parse_shorthand
from tests.conftest import FakeClient, make_issue, make_plan


def _subscribe(session, spec="sap web dispatcher, 4, 5, 1d"):
    return subscription_repo.create(session, parse_shorthand(spec))


def _fill(session, subscription, count: int) -> None:
    """Put `count` points on the ledger without going through generation."""
    series = engine.ensure_series(session, subscription)
    continuity.apply_issue(
        series=series,
        issue=make_issue(1, points=[f"established fact {i}" for i in range(count)]),
        delivery_id=None,
        tenant_id=subscription.tenant_id,
    )
    session.flush()


def test_no_compaction_below_the_trigger(session):
    sub = _subscribe(session)
    _fill(session, sub, COMPACT_TRIGGER - 1)
    assert continuity.needs_compaction(sub.series) is False


def test_compaction_triggers_at_the_cap(session):
    sub = _subscribe(session)
    _fill(session, sub, COMPACT_TRIGGER)
    assert continuity.needs_compaction(sub.series) is True


def test_compaction_takes_the_oldest_slice(session):
    sub = _subscribe(session)
    _fill(session, sub, COMPACT_TRIGGER)

    selected = continuity.points_to_compact(sub.series)

    assert len(selected) == COMPACT_OLDEST
    assert [p.point for p in selected] == [f"established fact {i}" for i in range(COMPACT_OLDEST)]


def test_compaction_keeps_originals_and_marks_them(session):
    """Nothing is deleted — a folded entry keeps its text and gains a timestamp."""
    sub = _subscribe(session)
    _fill(session, sub, COMPACT_TRIGGER)
    replaced = continuity.points_to_compact(sub.series)

    continuity.apply_compaction(
        series=sub.series,
        replaced=replaced,
        claims=["merged claim A", "merged claim B"],
        tenant_id=sub.tenant_id,
    )

    assert all(p.compacted_at is not None for p in replaced)
    assert all(p.point for p in replaced)  # text intact
    assert len(sub.series.coverage) == COMPACT_TRIGGER + 2  # nothing removed


def test_summaries_replace_originals_in_the_active_ledger(session):
    sub = _subscribe(session)
    _fill(session, sub, COMPACT_TRIGGER)
    replaced = continuity.points_to_compact(sub.series)

    continuity.apply_compaction(
        series=sub.series,
        replaced=replaced,
        claims=["merged claim A", "merged claim B"],
        tenant_id=sub.tenant_id,
    )

    active = continuity.active_points(sub.series)
    assert len(active) == COMPACT_TRIGGER - COMPACT_OLDEST + 2
    assert [p.point for p in active[:2]] == ["merged claim A", "merged claim B"]
    # Ordering survives: summaries sit where the entries they replace sat.
    assert active[2].point == f"established fact {COMPACT_OLDEST}"


def test_summaries_are_marked_as_summaries(session):
    sub = _subscribe(session)
    _fill(session, sub, COMPACT_TRIGGER)
    summaries = continuity.apply_compaction(
        series=sub.series,
        replaced=continuity.points_to_compact(sub.series),
        claims=["merged"],
        tenant_id=sub.tenant_id,
    )
    assert all(s.kind is CoverageKind.SUMMARY for s in summaries)


def test_summaries_are_themselves_compactable(session):
    """A long-running series must not accumulate an ever-growing tier of them."""
    sub = _subscribe(session)
    _fill(session, sub, COMPACT_TRIGGER)
    continuity.apply_compaction(
        series=sub.series,
        replaced=continuity.points_to_compact(sub.series),
        claims=[f"first-generation summary {i}" for i in range(20)],
        tenant_id=sub.tenant_id,
    )
    _fill(session, sub, COMPACT_OLDEST)  # push back over the trigger

    selected = continuity.points_to_compact(sub.series)

    assert any(p.kind is CoverageKind.SUMMARY for p in selected)


def test_new_points_land_after_compaction_without_colliding(session):
    sub = _subscribe(session)
    _fill(session, sub, COMPACT_TRIGGER)
    continuity.apply_compaction(
        series=sub.series,
        replaced=continuity.points_to_compact(sub.series),
        claims=["merged"],
        tenant_id=sub.tenant_id,
    )

    continuity.apply_issue(
        series=sub.series,
        issue=make_issue(2, points=["brand new"]),
        delivery_id=None,
        tenant_id=sub.tenant_id,
    )

    active = continuity.active_points(sub.series)
    assert active[-1].point == "brand new"


def test_empty_claims_are_a_no_op_rather_than_data_loss(session):
    """If the model returns nothing usable, keep the originals active."""
    sub = _subscribe(session)
    _fill(session, sub, COMPACT_TRIGGER)
    replaced = continuity.points_to_compact(sub.series)

    result = continuity.apply_compaction(
        series=sub.series, replaced=replaced, claims=["  ", ""], tenant_id=sub.tenant_id
    )

    assert result == []
    assert all(p.compacted_at is None for p in replaced)
    assert len(continuity.active_points(sub.series)) == COMPACT_TRIGGER


def test_target_is_a_quarter_and_never_zero():
    assert continuity.compaction_target(80) == 20
    assert continuity.compaction_target(2) == 1
    assert continuity.compaction_target(0) == 1


def test_engine_compacts_before_generating(session):
    sub = _subscribe(session)
    _fill(session, sub, COMPACT_TRIGGER)
    client = FakeClient(
        [
            CompactedLedger(claims=[f"merged {i}" for i in range(20)]),
            make_issue(2, points=["fresh point"]),
        ]
    )

    engine.generate_next(session=session, subscription=sub, client=client)

    # Compaction ran first, and the generation prompt saw the compacted ledger.
    assert client.calls[0]["model"] == "CompactedLedger"
    assert "merged 0" in client.calls[1]["user"]
    assert "established fact 0" not in client.calls[1]["user"]


def test_generation_survives_a_failed_compaction(session):
    """A compaction failure must not cost the reader their issue."""
    sub = _subscribe(session)
    _fill(session, sub, COMPACT_TRIGGER)

    class Failing(FakeClient):
        def generate(self, *, system, user, output_model):
            if output_model is CompactedLedger:
                from halflife.generation.client import GenerationError

                raise GenerationError("compaction unavailable")
            return super().generate(system=system, user=user, output_model=output_model)

    delivery = engine.generate_next(
        session=session, subscription=sub, client=Failing([make_issue(2)])
    )

    # The issue was still produced, and the compaction remains pending rather
    # than being silently marked done.
    assert delivery.title == "Issue 2"
    assert continuity.needs_compaction(sub.series) is True


def test_plan_generation_is_unaffected(session):
    sub = _subscribe(session)
    client = FakeClient([make_plan(3)])
    series = engine.plan_series(session=session, subscription=sub, client=client)
    assert len(series.plan) == 3
