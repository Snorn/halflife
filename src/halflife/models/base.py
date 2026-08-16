"""Declarative base, shared mixins, and the enums that appear in the schema.

Types here must work on both SQLite and Postgres. Enums are stored as VARCHAR
with a check constraint (``native_enum=False``) rather than as a Postgres ENUM,
because altering a native enum later is a migration you do not want.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class TenantMixin:
    """``tenant_id`` is first-class on every table from day one.

    Step 1 writes a constant. The point is that step 3 does not have to add a
    column to every table and backfill it.
    """

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)


class Frequency(str, enum.Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class Flavour(str, enum.Enum):
    """Labelled distinctly because they are different products to the reader.

    ``learning`` is a new topic. ``maintaining`` is a refresher on a skill the
    user already claims — gentler cadence, depth matched to claimed strength.
    """

    LEARNING = "learning"
    MAINTAINING = "maintaining"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"


class CoverageKind(str, enum.Enum):
    """A ledger row is either something an issue established, or a compaction of
    several such rows made when the ledger outgrew what fits in a prompt."""

    POINT = "point"
    SUMMARY = "summary"


class Feedback(str, enum.Enum):
    TOO_BASIC = "too_basic"
    JUST_RIGHT = "just_right"
    TOO_ADVANCED = "too_advanced"


MIN_DEPTH = 1
MAX_DEPTH = 5
