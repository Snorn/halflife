from __future__ import annotations

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


def list_unread(
    session: Session, *, tenant_id: str = LOCAL_TENANT_ID
) -> list[Delivery]:
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


def mark_read(session: Session, delivery: Delivery) -> Delivery:
    if delivery.read_at is None:
        delivery.read_at = utcnow()
        session.flush()
    return delivery


def set_feedback(session: Session, delivery: Delivery, feedback: Feedback) -> Delivery:
    delivery.feedback = feedback
    session.flush()
    return delivery
