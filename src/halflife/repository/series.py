from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from halflife.models.series import CoveragePoint, Series


def get_for_subscription(session: Session, subscription_id: str) -> Series | None:
    return session.scalar(select(Series).where(Series.subscription_id == subscription_id))


def coverage_points(
    session: Session, series_id: str, *, active_only: bool = False
) -> list[CoveragePoint]:
    stmt = select(CoveragePoint).where(CoveragePoint.series_id == series_id)
    if active_only:
        stmt = stmt.where(CoveragePoint.compacted_at.is_(None))
    return list(session.scalars(stmt.order_by(CoveragePoint.position)).all())
