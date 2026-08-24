"""Datetimes come back from the database aware, on every route.

Issue #4. SQLite has no timezone-aware type, so `DateTime(timezone=True)` was
silently inert and every stored value came back naive. It bit twice: a harness
converted due times to local and was a day out, and the daily-use gate
under-counted for as long as it was measured, because grouping naive values by
`.date()` groups them by UTC day.

The fix is a column type rather than a serialiser, so these test the boundary
every read passes through rather than the one surface where it was noticed.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from halflife import mcp_server
from halflife.db import session_scope
from halflife.models.base import Flavour, Frequency, utcnow
from halflife.models.subscription import Subscription
from halflife.repository import subscriptions as subscription_repo

PLUS_TEN = timezone(timedelta(hours=10))


def _subscribe(session, *, next_due_at: datetime) -> str:
    sub = Subscription(
        id="sub-utc",
        tenant_id="local",
        user_id="local",
        topic="timezones",
        depth=3,
        duration_minutes=5,
        frequency=Frequency.DAILY,
        flavour=Flavour.LEARNING,
        next_due_at=next_due_at,
    )
    session.add(sub)
    session.flush()
    return sub.id


def test_a_stored_datetime_comes_back_aware(migrated_db):
    with session_scope() as session:
        _subscribe(session, next_due_at=utcnow())

    with session_scope() as session:
        sub = subscription_repo.get(session, "sub-utc")
        assert sub.next_due_at.tzinfo is not None
        assert sub.next_due_at.utcoffset() == timedelta(0)


def test_an_aware_value_in_another_zone_is_stored_as_the_same_instant(migrated_db):
    """Written at 11:42 in +10, which is 01:42 UTC — the instant, not the clock."""
    local = datetime(2026, 8, 24, 11, 42, tzinfo=PLUS_TEN)

    with session_scope() as session:
        _subscribe(session, next_due_at=local)

    with session_scope() as session:
        sub = subscription_repo.get(session, "sub-utc")
        assert sub.next_due_at == local
        assert sub.next_due_at.hour == 1, "stored and returned as UTC"


def test_a_naive_value_is_taken_as_utc_rather_than_rejected(migrated_db):
    """Tolerant on the way in, strict on the way out: fixtures write naive."""
    with session_scope() as session:
        _subscribe(session, next_due_at=datetime(2026, 8, 24, 1, 42))

    with session_scope() as session:
        sub = subscription_repo.get(session, "sub-utc")
        assert sub.next_due_at == datetime(2026, 8, 24, 1, 42, tzinfo=timezone.utc)


def test_comparing_a_stored_value_against_utcnow_does_not_raise(migrated_db):
    """The step-3 landmine: on Postgres these are aware and naive comparison raises."""
    with session_scope() as session:
        _subscribe(session, next_due_at=utcnow() - timedelta(hours=1))

    with session_scope() as session:
        sub = subscription_repo.get(session, "sub-utc")
        assert sub.next_due_at < utcnow()  # would be TypeError against a naive value


def test_the_mcp_payload_carries_an_offset(migrated_db):
    """A harness must not have to guess the zone, which is how this was found."""
    with session_scope() as session:
        _subscribe(session, next_due_at=datetime(2026, 8, 24, 1, 42, tzinfo=timezone.utc))

    rows = json.loads(mcp_server.halflife_list_subscriptions())
    due = next(r["next_due_at"] for r in rows if r["subscription_id"] == "sub-utc")

    assert due == "2026-08-24T01:42:00+00:00"
    # Parseable without being told anything about it.
    assert datetime.fromisoformat(due).tzinfo is not None


@pytest.mark.parametrize("zone", [PLUS_TEN, timezone(timedelta(hours=-5)), timezone.utc])
def test_a_reader_can_convert_without_knowing_where_the_value_came_from(migrated_db, zone):
    with session_scope() as session:
        _subscribe(session, next_due_at=datetime(2026, 8, 24, 1, 42, tzinfo=timezone.utc))

    with session_scope() as session:
        sub = subscription_repo.get(session, "sub-utc")
        local = sub.next_due_at.astimezone(zone)

    assert local.utcoffset() == zone.utcoffset(None)
