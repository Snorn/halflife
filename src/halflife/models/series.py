"""Series continuity state.

Three parts, deliberately structured rather than a prose blob:

* ``Series.plan`` — an advisory arc sketched once at subscribe time, so the
  series does not random-walk around the topic.
* ``CoveragePoint`` — an append-only ledger, one short claim per row. This is
  what makes "do not repeat yourself" checkable instead of aspirational.
* ``Series.open_threads`` — things a previous issue explicitly deferred. Each
  generation must pick one up or drop it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from halflife.models.base import Base, TenantMixin, TimestampMixin, new_id


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
    open_threads: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    subscription: Mapped["Subscription"] = relationship(back_populates="series")  # noqa: F821
    coverage: Mapped[list["CoveragePoint"]] = relationship(
        back_populates="series", cascade="all, delete-orphan", order_by="CoveragePoint.position"
    )


class CoveragePoint(Base, TenantMixin, TimestampMixin):
    """One thing the series has already established. Append-only."""

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

    series: Mapped["Series"] = relationship(back_populates="coverage")
