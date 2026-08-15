from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from halflife.models.series import CoveragePoint, Series


def get_for_subscription(session: Session, subscription_id: str) -> Series | None:
    return session.scalar(select(Series).where(Series.subscription_id == subscription_id))


def coverage_points(session: Session, series_id: str) -> list[CoveragePoint]:
    stmt = (
        select(CoveragePoint)
        .where(CoveragePoint.series_id == series_id)
        .order_by(CoveragePoint.position)
    )
    return list(session.scalars(stmt).all())
