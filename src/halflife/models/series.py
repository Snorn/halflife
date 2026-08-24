"""Series continuity state.

Three parts, deliberately structured rather than a prose blob:

* ``Series.plan`` — an advisory arc sketched once at subscribe time, so the
  series does not random-walk around the topic.
* ``CoveragePoint`` — an append-only ledger, one short claim per row. This is
  what makes "do not repeat yourself" checkable instead of aspirational.
* ``Series.open_threads`` — things deferred by an issue or asked for by the
  reader. Each generation must pick one up or drop it. Each entry carries
  its source, because the reader's threads outrank the plan and a marker
  inferred from the text could be written by whatever wrote the text.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from halflife.models.base import (
    UtcDateTime,
    Base,
    CoverageKind,
    TenantMixin,
    TimestampMixin,
    new_id,
)


class Series(Base, TenantMixin, TimestampMixin):
    __tablename__ = "series"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subscription_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subscription.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    arc_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # [{"index": 1, "title": "...", "focus": "..."}, ...]
    plan: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    plan_prompt_version: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    # Replaced wholesale by each generation, so a list column rather than rows.
    # [{"text": "...", "source": "issue" | "reader"}, ...]
    open_threads: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    subscription: Mapped["Subscription"] = relationship(back_populates="series")  # noqa: F821
    coverage: Mapped[list["CoveragePoint"]] = relationship(
        back_populates="series", cascade="all, delete-orphan", order_by="CoveragePoint.position"
    )


class CoveragePoint(Base, TenantMixin, TimestampMixin):
    """One thing the series has already established. Append-only.

    Compaction never deletes: a row that has been folded into a summary keeps
    its text and gains a ``compacted_at``, which excludes it from the prompt but
    leaves the record of what the series actually said intact.
    """

    __tablename__ = "coverage_point"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    series_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("series.id", ondelete="CASCADE"), index=True, nullable=False
    )
    delivery_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("delivery.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    point: Mapped[str] = mapped_column(Text, nullable=False)

    kind: Mapped[CoverageKind] = mapped_column(
        Enum(
            CoverageKind,
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=CoverageKind.POINT,
        server_default=CoverageKind.POINT.value,
    )
    # Set when this row has been folded into a summary. Excluded from the
    # prompt from then on, but never removed.
    compacted_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )

    series: Mapped["Series"] = relationship(back_populates="coverage")

    @property
    def is_active(self) -> bool:
        return self.compacted_at is None
