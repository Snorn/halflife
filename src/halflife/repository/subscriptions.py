"""Subscription data access.

Repositories are the only place that touches the session. The CLI goes through
them, and so will the MCP server (step 2) and FastAPI (step 3).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from halflife import LOCAL_TENANT_ID, LOCAL_USER_ID
from halflife.models.base import (
    MAX_DEPTH,
    MIN_DEPTH,
    Feedback,
    Flavour,
    Frequency,
    SubscriptionStatus,
    new_id,
    utcnow,
)
from halflife.models.subscription import Subscription
from halflife.shorthand import ParsedSubscription


def create(
    session: Session,
    parsed: ParsedSubscription,
    *,
    tenant_id: str = LOCAL_TENANT_ID,
    user_id: str = LOCAL_USER_ID,
) -> Subscription:
    subscription = Subscription(
        id=new_id(),
        tenant_id=tenant_id,
        user_id=user_id,
        topic=parsed.topic,
        depth=parsed.depth,
        duration_minutes=parsed.duration_minutes,
        frequency=parsed.frequency,
        flavour=parsed.flavour,
        status=SubscriptionStatus.ACTIVE,
        next_due_at=utcnow(),
    )
    session.add(subscription)
    session.flush()
    return subscription


def get(session: Session, subscription_id: str) -> Subscription | None:
    return session.get(Subscription, subscription_id)


def get_by_prefix(session: Session, prefix: str) -> Subscription | None:
    """Look up by an id prefix, so the CLI can take the short form shown in `ls`."""
    matches = [
        s
        for s in session.scalars(select(Subscription)).all()
        if s.id.startswith(prefix)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def list_all(
    session: Session, *, tenant_id: str = LOCAL_TENANT_ID, include_paused: bool = True
) -> list[Subscription]:
    stmt = select(Subscription).where(Subscription.tenant_id == tenant_id)
    if not include_paused:
        stmt = stmt.where(Subscription.status == SubscriptionStatus.ACTIVE)
    return list(session.scalars(stmt.order_by(Subscription.created_at)).all())


def list_due(
    session: Session, *, now: datetime | None = None, tenant_id: str = LOCAL_TENANT_ID
) -> list[Subscription]:
    now = now or utcnow()
    stmt = (
        select(Subscription)
        .where(Subscription.tenant_id == tenant_id)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
        .where(Subscription.next_due_at <= now)
        .order_by(Subscription.next_due_at)
    )
    return list(session.scalars(stmt).all())


def set_status(
    session: Session, subscription: Subscription, status: SubscriptionStatus
) -> Subscription:
    subscription.status = status
    session.flush()
    return subscription


def apply_feedback_to_depth(
    session: Session, subscription: Subscription, feedback: Feedback
) -> int:
    """Nudge the subscription's depth in response to reader feedback.

    One step at a time, clamped. Feedback is the reader saying the *level* was
    wrong, so it moves depth and nothing else.
    """
    before = subscription.depth
    if feedback is Feedback.TOO_BASIC:
        subscription.depth = min(MAX_DEPTH, before + 1)
    elif feedback is Feedback.TOO_ADVANCED:
        subscription.depth = max(MIN_DEPTH, before - 1)
    session.flush()
    return subscription.depth


def update_parameters(
    session: Session,
    subscription: Subscription,
    *,
    depth: int | None = None,
    duration_minutes: int | None = None,
    frequency: Frequency | None = None,
    flavour: Flavour | None = None,
) -> Subscription:
    if depth is not None:
        subscription.depth = depth
    if duration_minutes is not None:
        subscription.duration_minutes = duration_minutes
    if frequency is not None:
        subscription.frequency = frequency
    if flavour is not None:
        subscription.flavour = flavour
    session.flush()
    return subscription
