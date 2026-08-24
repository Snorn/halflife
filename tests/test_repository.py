from __future__ import annotations

from datetime import timedelta

from types import SimpleNamespace

import pytest

from halflife import LOCAL_TENANT_ID
from halflife.models.base import Feedback, SubscriptionStatus, utcnow
from halflife.repository import subscriptions as subscription_repo
from halflife.shorthand import parse_shorthand


def _subscribe(session, spec="x, 3, 5, 1d"):
    return subscription_repo.create(session, parse_shorthand(spec))


def _rated(depth: int):
    """Stand-in for the delivery a rating is about; only its depth is read."""
    return SimpleNamespace(depth=depth)


def test_tenant_id_is_set_on_every_row(session):
    """Step 1 is single-tenant, but the column is populated from day one so
    step 3 is a deployment change rather than a backfill."""
    sub = _subscribe(session)
    assert sub.tenant_id == LOCAL_TENANT_ID


def test_new_subscription_is_immediately_due(session):
    sub = _subscribe(session)
    assert sub in subscription_repo.list_due(session)


def test_paused_subscriptions_are_never_due(session):
    sub = _subscribe(session)
    subscription_repo.set_status(session, sub, SubscriptionStatus.PAUSED)
    assert subscription_repo.list_due(session) == []


def test_not_yet_due_is_excluded(session):
    sub = _subscribe(session)
    sub.next_due_at = utcnow() + timedelta(hours=1)
    session.flush()
    assert subscription_repo.list_due(session) == []


@pytest.mark.parametrize(
    ("start", "verdict", "expected"),
    [
        (3, Feedback.TOO_BASIC, 4),
        (3, Feedback.TOO_ADVANCED, 2),
        (3, Feedback.JUST_RIGHT, 3),
        (5, Feedback.TOO_BASIC, 5),   # clamped at the top
        (1, Feedback.TOO_ADVANCED, 1),  # clamped at the bottom
    ],
)
def test_feedback_moves_depth_and_clamps(session, start, verdict, expected):
    """Rating an issue written at the subscription's own depth, the common case."""
    sub = _subscribe(session, f"x, {start}, 5, 1d")
    assert (
        subscription_repo.apply_feedback_to_depth(
            session, sub, verdict, rated=_rated(start)
        )
        == expected
    )


@pytest.mark.parametrize(
    "verdict", [Feedback.ALREADY_KNEW, Feedback.WRONG_SUBJECT]
)
def test_subject_feedback_leaves_depth_alone(session, verdict):
    """These say the level was right and the ground was wrong. Moving depth
    would answer a question the reader did not ask."""
    sub = _subscribe(session, "x, 3, 5, 1d")
    assert (
        subscription_repo.apply_feedback_to_depth(session, sub, verdict, rated=_rated(3))
        == 3
    )
    assert sub.depth == 3


def test_lookup_by_prefix(session):
    sub = _subscribe(session)
    assert subscription_repo.get_by_prefix(session, sub.id[:8]) is sub
    assert subscription_repo.get_by_prefix(session, "zzzzzzzz") is None


def test_advance_schedule_anchors_to_now_when_the_slot_lapsed(session):
    """A machine that was off for three days should not fire three issues."""
    sub = _subscribe(session, "x, 3, 5, 1d")
    sub.next_due_at = utcnow() - timedelta(days=3)
    session.flush()

    now = utcnow()
    sub.advance_schedule(now)

    assert sub.next_due_at == now + timedelta(days=1)
    assert subscription_repo.list_due(session) == []


def test_advance_schedule_keeps_the_slot_when_on_schedule(session):
    """The cadence-creep case scheduled delivery exposed.

    A fixed-time daily task writes a few minutes after the due time. Anchoring
    to `now` pushed the next slot past the next day's run, which then found
    nothing due — so delivery skipped every other day, forever, caused by the
    scheduler that exists to keep the cadence.
    """
    sub = _subscribe(session, "x, 3, 5, 1d")
    slot = utcnow() - timedelta(minutes=5)
    sub.next_due_at = slot
    session.flush()

    sub.advance_schedule(utcnow())  # written five minutes late, as a real run is

    assert sub.next_due_at == slot + timedelta(days=1), "the slot must not drift"


def test_advance_schedule_never_yields_a_slot_already_due(session):
    """The boundary between the two rules: a slot exactly one interval stale
    re-anchors, because keeping it would make the subscription due immediately."""
    sub = _subscribe(session, "x, 3, 5, 1d")
    sub.next_due_at = utcnow() - timedelta(days=1)
    session.flush()

    now = utcnow()
    sub.advance_schedule(now)

    assert sub.next_due_at > now


# ------------------------------------------------------------------ tenancy


OTHER_TENANT = "another-tenant"


def test_lookup_by_id_will_not_cross_tenants(session):
    """Step 1 has one tenant, so this is latent — but a repository that can
    return another tenant's row makes correctness the caller's problem, and
    step 3 has a lot of callers."""
    sub = _subscribe(session)

    assert subscription_repo.get(session, sub.id) is sub
    assert subscription_repo.get(session, sub.id, tenant_id=OTHER_TENANT) is None


def test_prefix_lookup_will_not_cross_tenants(session):
    sub = _subscribe(session)

    assert subscription_repo.get_by_prefix(session, sub.id[:8]) is sub
    assert subscription_repo.get_by_prefix(session, sub.id[:8], tenant_id=OTHER_TENANT) is None


def test_a_wildcard_prefix_matches_nothing(session):
    """The prefix arrives from a CLI argument or a model-supplied tool call.
    Under a bare LIKE, % would match every row and hand back a record the
    caller never named."""
    _subscribe(session)

    assert subscription_repo.get_by_prefix(session, "%") is None
    assert subscription_repo.get_by_prefix(session, "_") is None
    assert subscription_repo.get_by_prefix(session, "") is None


def test_an_underscore_is_matched_literally(session):
    """_ is a single-character wildcard in LIKE, so escaping has to leave it
    matching only itself."""
    sub = _subscribe(session)
    real = sub.id

    assert subscription_repo.get_by_prefix(session, real[0] + "_") is None
    assert subscription_repo.get_by_prefix(session, real[:8]) is sub


def test_an_ambiguous_prefix_still_returns_nothing(session):
    """Two rows share a prefix here only because they are given one; the point
    is that limiting the query did not turn ambiguity into a wrong answer."""
    first = _subscribe(session, "a, 3, 5, 1d")
    second = _subscribe(session, "b, 3, 5, 1d")
    first.id = "shared-prefix-1"
    second.id = "shared-prefix-2"
    session.flush()

    assert subscription_repo.get_by_prefix(session, "shared-prefix") is None
    assert subscription_repo.get_by_prefix(session, "shared-prefix-1") is first


# ------------------------------------------------------- the depth-1 cap


def _deliver(session, sub, n):
    from halflife.generation import engine
    from halflife.models.base import GenerationSource
    from tests.conftest import make_issue
    return engine.record_issue(
        session=session, subscription=sub, issue=make_issue(n),
        source=GenerationSource.HARNESS)


def test_only_depth_one_has_a_cap():
    """Orientation runs out of ground; interactions and internals do not, and
    the measurement behind that is beside ISSUE_CAP_BY_DEPTH."""
    from halflife.models.base import issue_cap

    assert issue_cap(1) == 3
    assert all(issue_cap(d) is None for d in (2, 3, 4, 5))


def test_a_depth_one_series_completes_at_the_cap(session):
    from halflife.models.base import issue_cap

    cap = issue_cap(1)
    sub = _subscribe(session, "x, 1, 5, 1d")

    for n in range(1, cap):
        _deliver(session, sub, n)
        assert subscription_repo.is_complete(sub) is False

    _deliver(session, sub, cap)
    assert subscription_repo.is_complete(sub) is True


def test_a_deeper_series_never_completes(session):
    sub = _subscribe(session, "x, 4, 5, 1d")

    for n in range(1, 7):
        _deliver(session, sub, n)

    assert subscription_repo.is_complete(sub) is False


def test_a_complete_series_is_not_due(session):
    """Due by the clock and having something left to write are different
    questions, and nothing downstream should have to know that."""
    from halflife.models.base import issue_cap

    sub = _subscribe(session, "x, 1, 5, 1d")
    for n in range(1, issue_cap(1) + 1):
        _deliver(session, sub, n)
    sub.next_due_at = utcnow()
    session.flush()

    assert subscription_repo.list_due(session) == []


def test_raising_the_depth_lets_a_complete_series_continue(session):
    """The escape hatch the completion message names: rate an issue too-basic,
    the depth moves to 2, and the cap no longer applies."""
    from halflife.models.base import issue_cap

    sub = _subscribe(session, "x, 1, 5, 1d")
    last = None
    for n in range(1, issue_cap(1) + 1):
        last = _deliver(session, sub, n)
    assert subscription_repo.is_complete(sub) is True

    subscription_repo.apply_feedback_to_depth(
        session, sub, Feedback.TOO_BASIC, rated=last
    )

    assert sub.depth == 2
    assert subscription_repo.is_complete(sub) is False


# Issue #9: depth moved one step per rating and never read the rated delivery's
# depth. With a backlog of unread issues all written at one depth, rating them
# honestly moved the depth once per rating — the reader answers a single
# question and the system counts each answer as a fresh instruction. Live: two
# issues written at depth 3 would have reached depth 1.


def test_rating_two_issues_of_the_same_depth_moves_the_depth_once(session):
    sub = _subscribe(session, "x, 3, 5, 1d")

    first = subscription_repo.apply_feedback_to_depth(
        session, sub, Feedback.TOO_ADVANCED, rated=_rated(3)
    )
    second = subscription_repo.apply_feedback_to_depth(
        session, sub, Feedback.TOO_ADVANCED, rated=_rated(3)
    )

    assert first == 2
    assert second == 2, "the second rating is about the same depth decision"


def test_the_same_holds_when_the_backlog_is_too_basic(session):
    sub = _subscribe(session, "x, 2, 5, 1d")

    for _ in range(3):
        depth = subscription_repo.apply_feedback_to_depth(
            session, sub, Feedback.TOO_BASIC, rated=_rated(2)
        )

    assert depth == 3


def test_successively_deeper_issues_still_progress(session):
    """Idempotence must not cost the ability to climb a level at a time."""
    sub = _subscribe(session, "x, 2, 5, 1d")

    subscription_repo.apply_feedback_to_depth(
        session, sub, Feedback.TOO_BASIC, rated=_rated(2)
    )
    assert sub.depth == 3

    # The next issue is written at 3, and is still too basic.
    subscription_repo.apply_feedback_to_depth(
        session, sub, Feedback.TOO_BASIC, rated=_rated(3)
    )
    assert sub.depth == 4


def test_a_rating_on_a_stale_issue_does_not_undo_a_later_correction(session):
    """Reading the backlog out of order must not walk the depth backwards."""
    sub = _subscribe(session, "x, 4, 5, 1d")

    subscription_repo.apply_feedback_to_depth(
        session, sub, Feedback.TOO_ADVANCED, rated=_rated(4)
    )
    assert sub.depth == 3

    # An older issue, written at 2, rated too_basic. It says "2 was too low",
    # which 3 already satisfies.
    subscription_repo.apply_feedback_to_depth(
        session, sub, Feedback.TOO_BASIC, rated=_rated(2)
    )
    assert sub.depth == 3
