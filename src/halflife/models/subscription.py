from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import CheckConstraint, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from halflife.models.base import (
    MAX_DEPTH,
    MIN_DEPTH,
    Base,
    Flavour,
    Frequency,
    SubscriptionStatus,
    TenantMixin,
    TimestampMixin,
    new_id,
    utcnow,
)

_INTERVALS: dict[Frequency, timedelta] = {
    Frequency.HOURLY: timedelta(hours=1),
    Frequency.DAILY: timedelta(days=1),
    Frequency.WEEKLY: timedelta(weeks=1),
}


class Subscription(Base, TenantMixin, TimestampMixin):
    __tablename__ = "subscription"
    __table_args__ = (
        CheckConstraint(
            f"depth >= {MIN_DEPTH} AND depth <= {MAX_DEPTH}", name="ck_subscription_depth"
        ),
        CheckConstraint("duration_minutes > 0", name="ck_subscription_duration"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    topic: Mapped[str] = mapped_column(String(256), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[Frequency] = mapped_column(
        Enum(Frequency, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    flavour: Mapped[Flavour] = mapped_column(
        Enum(Flavour, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=Flavour.LEARNING,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(
            SubscriptionStatus,
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
    )

    next_due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )
    last_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    series: Mapped["Series"] = relationship(  # noqa: F821
        back_populates="subscription", uselist=False, cascade="all, delete-orphan"
    )
    deliveries: Mapped[list["Delivery"]] = relationship(  # noqa: F821
        back_populates="subscription", cascade="all, delete-orphan", order_by="Delivery.issue_number"
    )

    @property
    def interval(self) -> timedelta:
        return _INTERVALS[self.frequency]

    def advance_schedule(self, now: datetime) -> None:
        """Move the subscription to its next slot.

        Anchored to *now* rather than to the previous due time so that a machine
        that was off for three days does not immediately fire three issues.
        """
        self.last_delivered_at = now
        self.next_due_at = now + self.interval

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Subscription {self.topic!r} depth={self.depth} "
            f"{self.duration_minutes}min {self.frequency.value}>"
        )
