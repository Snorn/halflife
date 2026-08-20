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


# The prefix is how a reader-raised thread keeps its provenance without a
# schema change. Open threads are a list of strings the generator already
# reads, and it is told to prefer these over the plan; a bare sentence would
# arrive indistinguishable from something a previous issue deferred.
READER_THREAD_PREFIX = "Asked for by the reader:"


def add_thread(session: Session, series: Series, text: str) -> list[str]:
    """Append a thread the reader raised, so the next issue is told about it.

    Threads are advisory and replaced wholesale when the next issue records its
    own, which is the existing behaviour and is left alone: a generator that
    takes the subject makes the thread disappear, and one that judges it not
    worth an issue drops it. Both are the mechanism working. What this cannot
    do is guarantee coverage, and nothing here pretends otherwise.
    """
    text = " ".join(text.split())
    if not text:
        return list(series.open_threads)

    thread = f"{READER_THREAD_PREFIX} {text}"
    if thread in series.open_threads:
        return list(series.open_threads)

    series.open_threads = list(series.open_threads) + [thread]
    session.flush()
    return list(series.open_threads)
