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


@pytest.mark.parametrize(
    "verdict", [Feedback.ALREADY_KNEW, Feedback.WRONG_SUBJECT]
)
def test_subject_feedback_leaves_depth_alone(session, verdict):
    """These say the level was right and the ground was wrong. Moving depth
    would answer a question the reader did not ask."""
    sub = _subscribe(session, "x, 3, 5, 1d")
    assert subscription_repo.apply_feedback_to_depth(session, sub, verdict) == 3
    assert sub.depth == 3


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
