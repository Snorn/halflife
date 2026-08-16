"""The generation engine.

``plan_series`` runs once when a subscription is created. ``generate_next``
runs once per issue: it renders the continuity state into the prompt, makes a
single API call that returns the body *and* the updated bookkeeping, and folds
the result back into the series.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from halflife.config import Settings, get_settings
from halflife.generation import continuity
from halflife.generation.client import GenerationClient, GenerationError
from halflife.generation.prompts import ledger_compaction, microlearning, series_plan
from halflife.generation.prompts.depth_rubric import DEPTH_RUBRIC_VERSION
from halflife.generation.schemas import CompactedLedger, GeneratedIssue, SeriesPlan
from halflife.models.base import new_id, utcnow
from halflife.models.delivery import Delivery
from halflife.models.series import CoveragePoint, Series
from halflife.models.subscription import Subscription

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


def plan_series(
    *,
    session: Session,
    subscription: Subscription,
    client: GenerationClient | None = None,
    settings: Settings | None = None,
) -> Series:
    """Sketch the series arc. Called once, at subscribe time."""
    settings = settings or get_settings()
    client = client or GenerationClient(settings)

    result = client.generate(
        system=series_plan.build_system_prompt(count=settings.series_plan_length),
        user=series_plan.build_user_prompt(
            topic=subscription.topic,
            depth=subscription.depth,
            duration_minutes=subscription.duration_minutes,
            flavour=subscription.flavour,
            count=settings.series_plan_length,
        ),
        output_model=SeriesPlan,
    )
    plan: SeriesPlan = result.parsed

    series = ensure_series(session, subscription)
    series.arc_summary = plan.arc_summary
    series.plan = continuity.plan_to_json(plan.issues)
    series.plan_prompt_version = series_plan.SERIES_PLAN_PROMPT_VERSION
    session.flush()
    return series


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


def generate_next(
    *,
    session: Session,
    subscription: Subscription,
    client: GenerationClient | None = None,
    settings: Settings | None = None,
) -> Delivery:
    """Generate the next issue of a subscription's series."""
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

    issue_number = series.issue_count + 1

    result = client.generate(
        system=microlearning.build_system_prompt(),
        user=microlearning.build_user_prompt(
            topic=subscription.topic,
            depth=subscription.depth,
            duration_minutes=subscription.duration_minutes,
            word_budget=word_budget(subscription.duration_minutes, settings),
            flavour=subscription.flavour,
            issue_number=issue_number,
            plan_block=continuity.render_plan_block(
                series.plan, series.arc_summary, issue_number
            ),
            ledger_block=continuity.render_ledger_block(
                [p.point for p in continuity.active_points(series)]
            ),
            threads_block=continuity.render_threads_block(list(series.open_threads)),
        ),
        output_model=GeneratedIssue,
    )
    issue: GeneratedIssue = result.parsed

    delivery = Delivery(
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
        model_id=result.model_id,
        effort=result.effort,
        depth_rubric_version=DEPTH_RUBRIC_VERSION,
        generation_prompt_version=microlearning.GENERATION_PROMPT_VERSION,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )
    session.add(delivery)

    continuity.apply_issue(
        series=series,
        issue=issue,
        delivery_id=delivery.id,
        tenant_id=subscription.tenant_id,
    )
    subscription.advance_schedule(utcnow())
    return delivery
