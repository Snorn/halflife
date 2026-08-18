from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from halflife import LOCAL_TENANT_ID
from halflife.models.base import Feedback, utcnow
from halflife.models.delivery import Delivery


def get(session: Session, delivery_id: str) -> Delivery | None:
    return session.get(Delivery, delivery_id)


def get_by_prefix(session: Session, prefix: str) -> Delivery | None:
    matches = [
        d for d in session.scalars(select(Delivery)).all() if d.id.startswith(prefix)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


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


def recent_subject_feedback(
    session: Session, subscription_id: str, *, limit: int = 3
) -> list[tuple[int, str, str]]:
    """The last few issues the reader said were mis-aimed rather than mis-pitched."""
    stmt = (
        select(Delivery)
        .where(Delivery.subscription_id == subscription_id)
        .where(Delivery.feedback.in_([Feedback.ALREADY_KNEW, Feedback.WRONG_SUBJECT]))
        .order_by(Delivery.issue_number.desc())
        .limit(limit)
    )
    rows = list(session.scalars(stmt).all())
    return [(d.issue_number, d.title, d.feedback.value) for d in reversed(rows)]


def mark_read(session: Session, delivery: Delivery) -> Delivery:
    if delivery.read_at is None:
        delivery.read_at = utcnow()
        session.flush()
    return delivery


def set_feedback(session: Session, delivery: Delivery, feedback: Feedback) -> Delivery:
    delivery.feedback = feedback
    session.flush()
    return delivery
