from __future__ import annotations

from datetime import timedelta

import pytest

from halflife import LOCAL_TENANT_ID
from halflife.models.base import Feedback, SubscriptionStatus, utcnow
from halflife.repository import subscriptions as subscription_repo
from halflife.shorthand import parse_shorthand


def _subscribe(session, spec="x, 3, 5, 1d"):
    return subscription_repo.create(session, parse_shorthand(spec))


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
def test_feedback_nudges_depth_one_step_and_clamps(session, start, verdict, expected):
    sub = _subscribe(session, f"x, {start}, 5, 1d")
    assert subscription_repo.apply_feedback_to_depth(session, sub, verdict) == expected


def test_lookup_by_prefix(session):
    sub = _subscribe(session)
    assert subscription_repo.get_by_prefix(session, sub.id[:8]) is sub
    assert subscription_repo.get_by_prefix(session, "zzzzzzzz") is None


def test_advance_schedule_anchors_to_now_not_to_the_missed_slot(session):
    """A machine that was off for three days should not fire three issues."""
    sub = _subscribe(session, "x, 3, 5, 1d")
    sub.next_due_at = utcnow() - timedelta(days=3)
    session.flush()

    now = utcnow()
    sub.advance_schedule(now)

    assert sub.next_due_at == now + timedelta(days=1)
    assert subscription_repo.list_due(session) == []
