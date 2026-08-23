"""Counting the days the reader actually used HalfLife.

This exists because the count was wrong for as long as it was computed by hand.
Timestamps are stored as UTC and come back from SQLite naive, so grouping them
by `.date()` counts UTC days — which for a reader east of Greenwich files their
early morning under the previous day. The G1 daily-use gate was under-reported
by a day and nothing about the number looked wrong.

Every test here pins a fixed timezone rather than using the machine's, because
a test whose result depends on where it runs cannot pin a timezone bug.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from halflife.db import session_scope
from halflife.models.base import Flavour, Frequency, GenerationSource, new_id, utcnow
from halflife.models.delivery import Delivery
from halflife.models.series import Series
from halflife.models.subscription import Subscription
from halflife.repository import deliveries as delivery_repo

PLUS_TEN = timezone(timedelta(hours=10))  # the reader's zone
MINUS_FIVE = timezone(timedelta(hours=-5))


SUB_ID = "sub-under-test"
SERIES_ID = "series-under-test"


def _subscription(session) -> None:
    """Deliveries carry foreign keys, so the parents have to exist."""
    session.add(
        Subscription(
            id=SUB_ID,
            tenant_id="local",
            user_id="local",
            topic="anything",
            depth=3,
            duration_minutes=5,
            frequency=Frequency.DAILY,
            flavour=Flavour.LEARNING,
            next_due_at=utcnow(),
        )
    )
    session.add(Series(id=SERIES_ID, tenant_id="local", subscription_id=SUB_ID))
    session.flush()


def _delivery(session, *, created, fetched=None, read=None, number=1) -> str:
    delivery = Delivery(
        id=new_id(),
        tenant_id="local",
        subscription_id=SUB_ID,
        series_id=SERIES_ID,
        issue_number=number,
        title="Issue",
        body_markdown="Body.",
        next_suggested="Next.",
        depth=3,
        duration_minutes=5,
        source=GenerationSource.HARNESS,
        depth_rubric_version="6",
        generation_prompt_version="4",
        created_at=created,
        updated_at=created,
        fetched_at=fetched,
        read_at=read,
    )
    session.add(delivery)
    return delivery.id


@pytest.fixture
def one_delivery_at(migrated_db):
    """Write a delivery whose stored UTC timestamp the caller chooses."""

    with session_scope() as session:
        _subscription(session)

    counter = {"n": 0}

    def _write(created: datetime) -> None:
        counter["n"] += 1
        with session_scope() as session:
            _delivery(session, created=created, number=counter["n"])

    return _write


def test_a_utc_evening_is_the_next_local_day_east_of_greenwich(one_delivery_at):
    """14:07 UTC is 00:07 the following day at +10. This is the actual bug."""
    one_delivery_at(datetime(2026, 8, 21, 14, 7))

    with session_scope() as session:
        days = delivery_repo.usage_days(session, tz=PLUS_TEN)

    assert days.written == {date(2026, 8, 22)}


def test_the_same_instant_is_the_previous_local_day_west_of_greenwich(one_delivery_at):
    one_delivery_at(datetime(2026, 8, 21, 2, 0))

    with session_scope() as session:
        days = delivery_repo.usage_days(session, tz=MINUS_FIVE)

    assert days.written == {date(2026, 8, 20)}


def test_two_utc_timestamps_one_local_day(one_delivery_at):
    """The count must not double-count either, which a naive fix could."""
    one_delivery_at(datetime(2026, 8, 21, 14, 7))  # 22nd, 00:07 local
    one_delivery_at(datetime(2026, 8, 22, 9, 0))  # 22nd, 19:00 local

    with session_scope() as session:
        days = delivery_repo.usage_days(session, tz=PLUS_TEN)

    assert days.written == {date(2026, 8, 22)}


def test_the_three_kinds_of_use_are_counted_separately(migrated_db):
    with session_scope() as session:
        _subscription(session)
        _delivery(
            session,
            created=datetime(2026, 8, 20, 1, 0),
            fetched=datetime(2026, 8, 21, 1, 0),
            read=datetime(2026, 8, 22, 1, 0),
        )

    with session_scope() as session:
        days = delivery_repo.usage_days(session, tz=PLUS_TEN)

    assert days.written == {date(2026, 8, 20)}
    assert days.fetched == {date(2026, 8, 21)}
    assert days.rated == {date(2026, 8, 22)}
    assert len(days.any_use) == 3


def test_read_only_days_exclude_days_something_was_written(migrated_db):
    """The gate's real question: opened on a day nothing was built for it."""
    with session_scope() as session:
        _subscription(session)
        # Written and read the same day — a building day, not a using day.
        _delivery(
            session,
            created=datetime(2026, 8, 20, 1, 0),
            read=datetime(2026, 8, 20, 2, 0),
            number=1,
        )
        # Read on a later day, with nothing written then.
        _delivery(
            session,
            created=datetime(2026, 8, 20, 1, 0),
            read=datetime(2026, 8, 25, 2, 0),
            number=2,
        )

    with session_scope() as session:
        days = delivery_repo.usage_days(session, tz=PLUS_TEN)

    assert days.read_only == {date(2026, 8, 25)}


def test_nulls_do_not_become_a_day(migrated_db):
    with session_scope() as session:
        _subscription(session)
        _delivery(session, created=datetime(2026, 8, 20, 1, 0))

    with session_scope() as session:
        days = delivery_repo.usage_days(session, tz=PLUS_TEN)

    assert days.fetched == frozenset()
    assert days.rated == frozenset()
