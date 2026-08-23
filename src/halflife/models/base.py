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


class GenerationSource(str, enum.Enum):
    """Which end wrote an issue.

    ``api`` is the control-plane path: pinned model, pinned effort, and the only
    one whose output is comparable across deliveries. ``harness`` means the
    user's own tool generated it, on whatever model that tool runs, which is why
    ``model_id`` and ``effort`` are nullable — recording an honest unknown beats
    recording a plausible fiction.
    """

    API = "api"
    HARNESS = "harness"


class Feedback(str, enum.Enum):
    """Two axes, deliberately separated.

    The first three are about *depth* and move the subscription's level. The
    last two are about *subject* and do not: they say the pitch was fine and
    the ground was wrong, which is a different complaint and needs a different
    response. Collapsing them, as a single scale does, loses the distinction
    entirely — a reader who already knew the material is not asking for
    something harder, they are asking for something else.
    """

    TOO_BASIC = "too_basic"
    JUST_RIGHT = "just_right"
    TOO_ADVANCED = "too_advanced"
    ALREADY_KNEW = "already_knew"
    WRONG_SUBJECT = "wrong_subject"

    @property
    def is_about_depth(self) -> bool:
        return self in {Feedback.TOO_BASIC, Feedback.JUST_RIGHT, Feedback.TOO_ADVANCED}


class SignalType(str, enum.Enum):
    """A coarse behavioural verb, never a score.

    Verbs survive the variance between one harness's model and another's; a
    number does not, and a number also invites being read as a competence
    rating of the person, which no signal here is.
    """

    ASKED_BASIC = "asked_basic"
    ASKED_ADVANCED = "asked_advanced"
    EXPLAINED_TO_AI = "explained_to_ai"
    APPLIED = "applied"
    STRUGGLED = "struggled"
    DELEGATED = "delegated"
    TOPIC_SUBMISSION = "topic_submission"


class Confidence(str, enum.Enum):
    """How sure the extracting agent is of its own classification.

    Not a competence score, and deliberately three coarse steps rather than a
    float: a number here would be averaged by somebody eventually, and the
    average of a model's self-assessment means nothing.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ContextCategory(str, enum.Enum):
    """What kind of work the session was, not what it was about."""

    CODING = "coding"
    TROUBLESHOOTING = "troubleshooting"
    RESEARCH = "research"
    WRITING = "writing"
    MEETING_PREP = "meeting-prep"


MIN_DEPTH = 1
MAX_DEPTH = 5

# A depth-1 series has a natural length, and it is short.
#
# Measured, not assumed. One depth-1 series was judged issue by issue against
# the ledger its writer actually saw: 0 points -> depth 1, 11 -> 1, 21 -> 1,
# and 36 -> depth 4. A depth-4 series at the same ledger sizes held at 4
# throughout, so this is not deep ledgers pushing everything upward — it is
# orientation running out of ground. "What it is and what problem it solves" is
# a finite amount of material, and once the ledger holds it, a writer forbidden
# to re-explain any of it has nothing left to say at that level.
#
# Two prompt revisions were tried against this and both failed, including one
# that explicitly offered "go sideways rather than up" as the legal move. The
# prompt is the wrong place to fix it, so the series simply ends.
#
# Only depth 1 is capped. Nothing above it runs out: interactions, second-order
# effects and internals are unbounded, and the measurement says so.
#
# The unit is issues rather than ledger points because it is the number a
# reader can see and reason about before subscribing. It is a proxy: the real
# variable is ledger size, and at the ~12 points an issue this project
# measures, three issues is where the ground still holds. A series whose issues
# establish far more or far less than that will hit the wall at a different
# number.
#
# Three rather than four because the measurement puts the failure *at* the
# fourth issue: it saw 36 ledger points and was judged three levels off, while
# the third saw 21 and held. A cap of four would have shipped the issue that
# broke. The cost of being wrong is asymmetric — a series that stops one issue
# early loses one orientation piece, while one that stops one issue late
# delivers a piece at the wrong level, which is the failure the depth rubric
# exists to prevent.
class ThreadSource(str, enum.Enum):
    """Who raised an open thread.

    Stored on the thread rather than inferred from its text. It was a string
    prefix, and `render_threads_block` decided a thread came from the reader by
    matching it — which a harness could write itself, promoting its own text
    into the channel the prompt says outranks the plan. A marker the content
    supplies about itself is not a marker. Issue #8.

    The harness never sends this field: `record_issue` takes plain strings and
    the repository stamps ISSUE. There is no request shape that lets a caller
    claim READER.
    """

    ISSUE = "issue"
    READER = "reader"


def thread(text: str, source: ThreadSource) -> dict[str, str]:
    """One stored open thread. A dict because the column is JSON."""
    return {"text": text, "source": source.value}


def is_reader_thread(entry: dict[str, str]) -> bool:
    return entry.get("source") == ThreadSource.READER.value


ISSUE_CAP_BY_DEPTH = {1: 3}


def issue_cap(depth: int) -> int | None:
    """How many issues this depth supports, or None if it does not run out."""
    return ISSUE_CAP_BY_DEPTH.get(depth)

# Bumped when the signal envelope or body changes shape, so a control plane can
# tell which contract a stored row was written against.
SIGNAL_SCHEMA_VERSION = "1"
