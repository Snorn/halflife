"""The generation engine.

``plan_series`` runs once when a subscription is created. ``generate_next``
runs once per issue: it renders the continuity state into the prompt, makes a
single API call that returns the body *and* the updated bookkeeping, and folds
the result back into the series.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from halflife.config import Settings, get_settings
from halflife.generation import continuity
from halflife.generation.client import GenerationClient, GenerationError
from halflife.generation.prompts import ledger_compaction, microlearning, series_plan
from halflife.generation.prompts.depth_rubric import DEPTH_RUBRIC_VERSION
from halflife.generation.schemas import (
    CompactedLedger,
    GeneratedIssue,
    PlannedIssue,
    SeriesPlan,
)
from halflife.models.base import GenerationSource, new_id, utcnow
from halflife.models.delivery import Delivery
from halflife.models.series import CoveragePoint, Series
from halflife.models.subscription import Subscription
from halflife.repository import deliveries as delivery_repo

log = logging.getLogger(__name__)


def word_budget(duration_minutes: int, settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    return duration_minutes * settings.words_per_minute


def ensure_series(session: Session, subscription: Subscription) -> Series:
    """Every subscription has a series, planned or not.

    A series with an empty plan is a legitimate state — the reader can opt out
    of the arc — and generation falls back to choosing each subject from the
    coverage ledger alone.
    """
    if subscription.series is not None:
        return subscription.series

    series = Series(
        id=new_id(),
        tenant_id=subscription.tenant_id,
        subscription_id=subscription.id,
        arc_summary="",
        plan=[],
        plan_prompt_version="",
        open_threads=[],
        issue_count=0,
    )
    subscription.series = series
    session.add(series)
    session.flush()
    return series


@dataclass(frozen=True)
class PlanBrief:
    """The plan equivalent of IssueBrief.

    Without this a harness-only install could never draw an arc, and every
    series would run unplanned — which the plan A/B measured as worse: the
    unplanned arm front-loaded its first issue with conclusions belonging to
    issues four to six, leaving the later ones to re-derive rather than build.
    """

    subscription_id: str
    topic: str
    depth: int
    duration_minutes: int
    flavour: str
    count: int
    already_planned: bool
    system_prompt: str
    user_prompt: str


def build_plan_brief(
    *,
    session: Session,
    subscription: Subscription,
    settings: Settings | None = None,
) -> PlanBrief:
    """Assemble the series-planning prompt without generating anything."""
    settings = settings or get_settings()
    series = ensure_series(session, subscription)
    count = settings.series_plan_length

    return PlanBrief(
        subscription_id=subscription.id,
        topic=subscription.topic,
        depth=subscription.depth,
        duration_minutes=subscription.duration_minutes,
        flavour=subscription.flavour.value,
        count=count,
        already_planned=bool(series.plan),
        system_prompt=series_plan.build_system_prompt(count=count),
        user_prompt=series_plan.build_user_prompt(
            topic=subscription.topic,
            depth=subscription.depth,
            duration_minutes=subscription.duration_minutes,
            flavour=subscription.flavour,
            count=count,
        ),
    )


def record_plan(
    *,
    session: Session,
    subscription: Subscription,
    arc_summary: str,
    issues: list[PlannedIssue],
) -> Series:
    """Store a series arc, replacing any existing one.

    Replacing rather than refusing: a series whose plan has been overtaken by
    what the reader actually needs is better re-planned than left misleading,
    and the coverage ledger — not the plan — is what protects continuity.
    """
    series = ensure_series(session, subscription)
    series.arc_summary = arc_summary.strip()
    series.plan = continuity.plan_to_json(issues)
    series.plan_prompt_version = series_plan.SERIES_PLAN_PROMPT_VERSION
    session.flush()
    return series


def plan_series(
    *,
    session: Session,
    subscription: Subscription,
    client: GenerationClient | None = None,
    settings: Settings | None = None,
) -> Series:
    """Sketch the series arc via the API. Called once, at subscribe time."""
    settings = settings or get_settings()
    client = client or GenerationClient(settings)

    brief = build_plan_brief(session=session, subscription=subscription, settings=settings)
    result = client.generate(
        system=brief.system_prompt,
        user=brief.user_prompt,
        output_model=SeriesPlan,
    )
    plan: SeriesPlan = result.parsed

    return record_plan(
        session=session,
        subscription=subscription,
        arc_summary=plan.arc_summary,
        issues=plan.issues,
    )


@dataclass(frozen=True)
class CompactionBrief:
    """The compaction equivalent of IssueBrief.

    Without this, a harness-only install would hit the ledger cap around issue
    fifteen and silently fall back to truncating its oldest entries — the exact
    failure compaction exists to prevent.
    """

    subscription_id: str
    topic: str
    entry_count: int
    target: int
    system_prompt: str
    user_prompt: str


def build_compaction_brief(
    *,
    session: Session,
    subscription: Subscription,
) -> CompactionBrief | None:
    """None when there is nothing to compact."""
    series = ensure_series(session, subscription)
    replaced = continuity.points_to_compact(series)
    if not replaced:
        return None

    entries = [p.point for p in replaced]
    target = continuity.compaction_target(len(entries))
    return CompactionBrief(
        subscription_id=subscription.id,
        topic=subscription.topic,
        entry_count=len(entries),
        target=target,
        system_prompt=ledger_compaction.build_system_prompt(),
        user_prompt=ledger_compaction.build_user_prompt(
            topic=subscription.topic, entries=entries, target=target
        ),
    )


def record_compaction(
    *,
    session: Session,
    subscription: Subscription,
    claims: list[str],
) -> list[CoveragePoint]:
    """Fold the oldest slice into the given claims."""
    series = ensure_series(session, subscription)
    replaced = continuity.points_to_compact(series)
    if not replaced:
        return []

    summaries = continuity.apply_compaction(
        series=series,
        replaced=replaced,
        claims=claims,
        tenant_id=subscription.tenant_id,
    )
    session.flush()
    return summaries


def compact_ledger(
    *,
    session: Session,
    subscription: Subscription,
    client: GenerationClient | None = None,
    settings: Settings | None = None,
) -> list[CoveragePoint]:
    """Fold the oldest part of the ledger into fewer, denser claims.

    Costs one API call, and happens roughly every five or six issues once a
    series is past its second week.
    """
    settings = settings or get_settings()
    client = client or GenerationClient(settings)

    series = ensure_series(session, subscription)
    replaced = continuity.points_to_compact(series)
    if not replaced:
        return []

    result = client.generate(
        system=ledger_compaction.build_system_prompt(),
        user=ledger_compaction.build_user_prompt(
            topic=subscription.topic,
            entries=[p.point for p in replaced],
            target=continuity.compaction_target(len(replaced)),
        ),
        output_model=CompactedLedger,
    )

    summaries = continuity.apply_compaction(
        series=series,
        replaced=replaced,
        claims=result.parsed.claims,
        tenant_id=subscription.tenant_id,
    )
    session.flush()
    log.info(
        "Compacted %d ledger entries into %d for %r",
        len(replaced),
        len(summaries),
        subscription.topic,
    )
    return summaries


@dataclass(frozen=True)
class IssueBrief:
    """Everything needed to write one issue, and nothing that writes it.

    This is the seam that lets a harness generate instead of the API: the same
    prompts, the same continuity state, handed out rather than sent to a model.
    """

    subscription_id: str
    topic: str
    depth: int
    duration_minutes: int
    word_budget: int
    flavour: str
    issue_number: int
    system_prompt: str
    user_prompt: str
    ledger_size: int
    needs_compaction: bool


def build_brief(
    *,
    session: Session,
    subscription: Subscription,
    settings: Settings | None = None,
) -> IssueBrief:
    """Assemble the prompt for the next issue without generating anything."""
    settings = settings or get_settings()
    series = ensure_series(session, subscription)
    issue_number = series.issue_count + 1
    active = continuity.active_points(series)
    subject_feedback = delivery_repo.subject_feedback(session, subscription.id)

    return IssueBrief(
        subscription_id=subscription.id,
        topic=subscription.topic,
        depth=subscription.depth,
        duration_minutes=subscription.duration_minutes,
        word_budget=word_budget(subscription.duration_minutes, settings),
        flavour=subscription.flavour.value,
        issue_number=issue_number,
        system_prompt=microlearning.build_system_prompt(),
        user_prompt=microlearning.build_user_prompt(
            topic=subscription.topic,
            depth=subscription.depth,
            duration_minutes=subscription.duration_minutes,
            word_budget=word_budget(subscription.duration_minutes, settings),
            flavour=subscription.flavour,
            issue_number=issue_number,
            plan_block=continuity.render_plan_block(
                series.plan,
                series.arc_summary,
                issue_number,
                written=delivery_repo.plan_entries_written(session, subscription.id),
                rejected={
                    f.plan_index: f.verdict
                    for f in subject_feedback
                    if f.plan_index is not None
                },
            ),
            ledger_block=continuity.render_ledger_block([p.point for p in active]),
            threads_block=continuity.render_threads_block(list(series.open_threads)),
            feedback_block=continuity.render_feedback_block(subject_feedback),
        ),
        ledger_size=len(active),
        needs_compaction=continuity.needs_compaction(series),
    )


def _reported_plan_index(series: Series, reported: int) -> int:
    """Which plan entry the generation says it took, or 0 for none of them.

    0 is a real answer — it took an open thread or went its own way, which the
    prompt permits — and is stored as 0 rather than null, because null is
    reserved for rows written before generation reported this at all. An index
    the plan does not contain collapses to 0: a number that cannot be checked
    against the plan says no more than saying nothing did.
    """
    known = {entry.get("index") for entry in series.plan}
    return reported if reported in known else 0


def record_issue(
    *,
    session: Session,
    subscription: Subscription,
    issue: GeneratedIssue,
    source: GenerationSource,
    model_id: str | None = None,
    effort: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> Delivery:
    """Persist a written issue and fold it into the series.

    Identical bookkeeping whichever end wrote it — the only difference recorded
    is ``source``, so eval analysis can separate API-generated issues from ones
    a harness produced on an unknown model.
    """
    series = ensure_series(session, subscription)
    issue_number = series.issue_count + 1

    delivery = Delivery(
        plan_index=_reported_plan_index(series, issue.plan_index),
        id=new_id(),
        tenant_id=subscription.tenant_id,
        subscription_id=subscription.id,
        series_id=series.id,
        issue_number=issue_number,
        title=issue.title.strip(),
        body_markdown=issue.body_markdown.strip(),
        next_suggested=issue.next_suggested.strip(),
        depth=subscription.depth,
        duration_minutes=subscription.duration_minutes,
        source=source,
        model_id=model_id,
        effort=effort,
        depth_rubric_version=DEPTH_RUBRIC_VERSION,
        generation_prompt_version=microlearning.GENERATION_PROMPT_VERSION,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    session.add(delivery)

    continuity.apply_issue(
        series=series,
        issue=issue,
        delivery_id=delivery.id,
        tenant_id=subscription.tenant_id,
    )
    subscription.advance_schedule(utcnow())
    session.flush()
    return delivery


def generate_next(
    *,
    session: Session,
    subscription: Subscription,
    client: GenerationClient | None = None,
    settings: Settings | None = None,
) -> Delivery:
    """Generate the next issue via the API. The maintainer path."""
    settings = settings or get_settings()
    client = client or GenerationClient(settings)

    series = ensure_series(session, subscription)

    if continuity.needs_compaction(series):
        try:
            compact_ledger(
                session=session, subscription=subscription, client=client, settings=settings
            )
        except GenerationError:
            # A failed compaction must not cost the reader their issue. The
            # render path truncates as a backstop, which is worse than a
            # compaction but not worth failing over.
            log.warning("Ledger compaction failed; generating against a truncated ledger.")

    brief = build_brief(session=session, subscription=subscription, settings=settings)

    result = client.generate(
        system=brief.system_prompt,
        user=brief.user_prompt,
        output_model=GeneratedIssue,
    )

    return record_issue(
        session=session,
        subscription=subscription,
        issue=result.parsed,
        source=GenerationSource.API,
        model_id=result.model_id,
        effort=result.effort,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
