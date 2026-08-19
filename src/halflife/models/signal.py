"""The signal table — the privacy boundary, in schema form.

Read CLAUDE.md's privacy section before changing anything here. The short
version is that a signal records *that* a kind of interaction happened with a
named subject, and nothing whatever about what was said.

Two columns carry most of the weight of that claim.

``evidence`` exists and stays null. It is not a staging area and not a debug
hook: it is here so that anyone auditing the schema can see the field where
excerpts would live and confirm that nothing populates it. The repository
refuses to write a row with anything in it.

``session_id`` is a digest. It exists to let two signals from one sitting be
recognised as related without any way back to the sitting itself. Nothing
upstream stores the value it was derived from.

There is deliberately no relationship from Signal to Subscription or Delivery.
Signals are write-only inputs to time-windowed aggregates; a foreign key would
be the first step towards a per-signal read path, which CLAUDE.md forbids.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from halflife.models.base import (
    Base,
    Confidence,
    ContextCategory,
    SignalType,
    TenantMixin,
    TimestampMixin,
    new_id,
)


class Signal(Base, TenantMixin, TimestampMixin):
    """One classified observation. No content, by construction."""

    __tablename__ = "signal"
    __table_args__ = (
        # Aggregates are time-windowed and per-user; nothing queries a signal
        # by its own id, so that is the index that does not exist.
        Index("ix_signal_window", "tenant_id", "user_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # When the interaction happened, as reported by the agent — distinct from
    # created_at, which is when this row was written.
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # A digest. Never the value it came from.
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Free text at the edge, normalised centrally: the taxonomy never ships to
    # the agent, so these arrive as whatever the subject is actually called.
    topics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    signal_type: Mapped[SignalType] = mapped_column(
        Enum(SignalType, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    confidence: Mapped[Confidence] = mapped_column(
        Enum(Confidence, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    context_category: Mapped[ContextCategory] = mapped_column(
        Enum(ContextCategory, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )

    # Permanently null in v1. Present so the privacy stance is inspectable
    # rather than promised; the repository rejects any attempt to fill it.
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # Which agent produced this, so a bad extraction prompt version can be
    # identified and excluded rather than guessed at.
    harness: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(32), nullable=False)
    extraction_prompt_version: Mapped[str] = mapped_column(String(16), nullable=False)
