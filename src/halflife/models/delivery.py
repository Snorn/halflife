from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from halflife.models.base import (
    Base,
    Feedback,
    GenerationSource,
    TenantMixin,
    TimestampMixin,
    new_id,
)


class Delivery(Base, TenantMixin, TimestampMixin):
    """One generated issue of a series.

    The prompt-version columns are not bookkeeping for its own sake: without
    them the eval harness cannot attribute a change in quality to a change in
    a prompt.
    """

    __tablename__ = "delivery"
    __table_args__ = (
        UniqueConstraint("subscription_id", "issue_number", name="uq_delivery_issue"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subscription_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subscription.id", ondelete="CASCADE"), index=True, nullable=False
    )
    series_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("series.id", ondelete="CASCADE"), index=True, nullable=False
    )

    issue_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    next_suggested: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Which series-plan entry this issue took. 0 means it took none of them,
    # which the prompt permits; null means the row predates generation
    # reporting it, and is the only case anything falls back to guessing.
    plan_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # The parameters actually used, which may differ from the subscription's
    # current values if feedback has since adjusted them.
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    source: Mapped[GenerationSource] = mapped_column(
        Enum(
            GenerationSource,
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=GenerationSource.API,
        server_default=GenerationSource.API.value,
    )
    # Nullable because a harness may not report what it ran. An honest unknown
    # is worth more than a plausible default when attributing quality.
    model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effort: Mapped[str | None] = mapped_column(String(16), nullable=True)
    depth_rubric_version: Mapped[str] = mapped_column(String(16), nullable=False)
    generation_prompt_version: Mapped[str] = mapped_column(String(16), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback: Mapped[Feedback | None] = mapped_column(
        Enum(Feedback, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )

    subscription: Mapped["Subscription"] = relationship(back_populates="deliveries")  # noqa: F821
