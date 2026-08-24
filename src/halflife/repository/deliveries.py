from __future__ import annotations

from datetime import date, datetime, timezone, tzinfo
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from halflife import LOCAL_TENANT_ID
from halflife.models.base import Feedback, utcnow
from halflife.models.delivery import Delivery
from halflife.repository._prefix import prefix_match


def get(
    session: Session, delivery_id: str, *, tenant_id: str = LOCAL_TENANT_ID
) -> Delivery | None:
    """Fetch by id, within one tenant. Another tenant's row reads as absent."""
    delivery = session.get(Delivery, delivery_id)
    if delivery is None or delivery.tenant_id != tenant_id:
        return None
    return delivery


def get_by_prefix(
    session: Session, prefix: str, *, tenant_id: str = LOCAL_TENANT_ID
) -> Delivery | None:
    if not prefix:
        return None
    stmt = (
        select(Delivery)
        .where(Delivery.tenant_id == tenant_id)
        .where(prefix_match(Delivery.id, prefix))
        .limit(2)
    )
    matches = list(session.scalars(stmt).all())
    return matches[0] if len(matches) == 1 else None


def list_recent(
    session: Session, *, limit: int = 20, tenant_id: str = LOCAL_TENANT_ID
) -> list[Delivery]:
    stmt = (
        select(Delivery)
        .where(Delivery.tenant_id == tenant_id)
        .order_by(Delivery.created_at.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def list_unacknowledged(
    session: Session, *, tenant_id: str = LOCAL_TENANT_ID
) -> list[Delivery]:
    """Deliveries the reader has not acknowledged, fetched or not.

    An issue leaves this list by being rated, not by having its text read out
    of the database. Fetching is not evidence a person saw anything — that is
    the whole finding behind splitting the column — so a delivery that was
    displayed and never rated stays here, which is the honest state.
    """
    stmt = (
        select(Delivery)
        .where(Delivery.tenant_id == tenant_id)
        .where(Delivery.read_at.is_(None))
        .order_by(Delivery.created_at)
    )
    return list(session.scalars(stmt).all())


def list_for_subscription(session: Session, subscription_id: str) -> list[Delivery]:
    stmt = (
        select(Delivery)
        .where(Delivery.subscription_id == subscription_id)
        .order_by(Delivery.issue_number)
    )
    return list(session.scalars(stmt).all())


class SubjectFeedback(NamedTuple):
    """One issue the reader said was mis-aimed rather than mis-pitched."""

    issue_number: int
    title: str
    verdict: str
    plan_index: int | None


def subject_feedback(session: Session, subscription_id: str) -> list[SubjectFeedback]:
    """Every rejection on this subscription, oldest first.

    All of them, not a recent slice: the plan block marks each rejected entry
    for the life of the series, and it is the prompt renderer that decides how
    many to spell out in prose.
    """
    stmt = (
        select(Delivery)
        .where(Delivery.subscription_id == subscription_id)
        .where(Delivery.feedback.in_([Feedback.ALREADY_KNEW, Feedback.WRONG_SUBJECT]))
        .order_by(Delivery.issue_number)
    )
    return [
        SubjectFeedback(d.issue_number, d.title, d.feedback.value, d.plan_index)
        for d in session.scalars(stmt).all()
    ]


def plan_entries_written(session: Session, subscription_id: str) -> set[int]:
    """Series-plan entries that an issue actually covered.

    Rows written before generation reported a plan index fall back to matching
    entry number against issue number. That is the guess this column exists to
    remove, but dropping the marker for those rows would leave the generator
    free to cover them again, which is the worse failure.
    """
    stmt = (
        select(Delivery)
        .where(Delivery.subscription_id == subscription_id)
        .order_by(Delivery.issue_number)
    )
    written: set[int] = set()
    for delivery in session.scalars(stmt).all():
        if delivery.plan_index is None:
            written.add(delivery.issue_number)
        elif delivery.plan_index > 0:
            written.add(delivery.plan_index)
    return written


def mark_fetched(session: Session, delivery: Delivery) -> Delivery:
    """The text left the database. Says nothing about anybody having read it."""
    if delivery.fetched_at is None:
        delivery.fetched_at = utcnow()
        session.flush()
    return delivery


def set_feedback(session: Session, delivery: Delivery, feedback: Feedback) -> Delivery:
    """Record a rating, which is also the only acknowledgement of a read.

    A rating cannot be produced by a fetch, a summary or a display, so it is
    the one event in the system that establishes a person engaged with the
    text. read_at is set here and nowhere else, deliberately: every other
    candidate turned out to be a receipt for a code path rather than for a
    reader.

    First rating wins. A reader who changes their mind is re-rating something
    they read once, and moving the timestamp forward would misdate the reading.
    """
    delivery.feedback = feedback
    if delivery.read_at is None:
        delivery.read_at = utcnow()
    session.flush()
    return delivery


class UsageDays(NamedTuple):
    """Distinct local dates on which the tool was used, by kind of use."""

    written: frozenset[date]
    fetched: frozenset[date]
    rated: frozenset[date]

    @property
    def any_use(self) -> frozenset[date]:
        return self.written | self.fetched | self.rated

    @property
    def read_only(self) -> frozenset[date]:
        """Days something was read or rated but nothing was generated.

        The gate asks whether the tool is opened on a day when nothing is being
        built for it. A day that only appears here is the closest evidence of
        that the data holds.
        """
        return (self.fetched | self.rated) - self.written


def usage_days(
    session: Session, *, tz: tzinfo | None = None, tenant_id: str = LOCAL_TENANT_ID
) -> UsageDays:
    """Which days the reader used HalfLife, in the reader's own timezone.

    Timestamps are stored as UTC and SQLite hands them back naive, so grouping
    them by ``.date()`` counts UTC days. For a reader at UTC+10 that silently
    files everything before 10am local under the previous day, and the count
    comes out short without ever looking wrong. That is not hypothetical: it
    under-reported the daily-use gate by a day for as long as the gate was
    measured by hand.

    ``tz`` defaults to the machine's local zone, which is correct while there
    is one reader on one machine. When there is a server this needs a stored
    per-user zone instead, and the default here becomes wrong rather than
    merely approximate.
    """
    zone = tz or datetime.now().astimezone().tzinfo

    def local_dates(values) -> frozenset[date]:
        # Values arrive aware: UtcDateTime guarantees it. This used to attach
        # UTC itself, which was correct and is now a lie about where the
        # guarantee lives.
        return frozenset(v.astimezone(zone).date() for v in values if v is not None)

    rows = list(
        session.scalars(select(Delivery).where(Delivery.tenant_id == tenant_id)).all()
    )
    return UsageDays(
        written=local_dates(d.created_at for d in rows),
        fetched=local_dates(d.fetched_at for d in rows),
        rated=local_dates(d.read_at for d in rows),
    )
