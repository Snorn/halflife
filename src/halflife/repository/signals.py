"""Signal data access — deliberately almost empty.

CLAUDE.md's aggregation rule: raw signals are write-only inputs, every
human-visible surface is built from time-windowed aggregates, and nobody
browses individual signals, including org admins. So there is no ``get``, no
``get_by_prefix`` and no ``list_all`` here, and their absence is the feature.
The moment one exists "for debugging", the boundary is a policy rather than a
shape.

Writing goes through ``extraction.engine.record_signals``. What lives here is
the guard that runs before a row is allowed to persist.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from halflife import LOCAL_TENANT_ID
from halflife.models.signal import Signal


class PrivacyViolation(RuntimeError):
    """A signal carried something it is not allowed to carry."""


def assert_no_content(signal: Signal) -> None:
    """Refuse to store a row with evidence in it.

    ``evidence`` is permanently null in v1. The column exists so the stance can
    be audited, and this is what makes it true rather than intended: a future
    change that starts populating it fails here instead of shipping.
    """
    if signal.evidence is not None:
        raise PrivacyViolation(
            "evidence is permanently null in v1 — see the privacy boundary in CLAUDE.md. "
            "Nothing may populate it, including a debug mode."
        )


def count_in_window(
    session: Session,
    *,
    since,
    tenant_id: str = LOCAL_TENANT_ID,
) -> int:
    """How many signals landed since a moment in time.

    An aggregate, and the smallest one that is useful: it answers "is anything
    being captured at all" without exposing a single row. Deliberately returns
    a number rather than the rows behind it.
    """
    stmt = (
        select(func.count())
        .select_from(Signal)
        .where(Signal.tenant_id == tenant_id)
        .where(Signal.occurred_at >= since)
    )
    return int(session.scalar(stmt) or 0)
