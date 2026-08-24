"""MCP server — in-harness delivery, and in-harness generation.

Step 2. The engine's own model call becomes optional here: instead of HalfLife
calling a model, the harness calls HalfLife. ``next_brief`` hands out the
assembled prompt, the harness's own model writes the issue, and ``record_issue``
takes it back and does the bookkeeping.

That inversion is why this works where an API key is not available: the model is
the one the user is already approved to use. It also matches the design doc's
own rule that the agent is thick and uses the harness's model — generation was
the carved-out exception, and this removes the exception.

What it costs: nothing generates unless a session is open, and the model is
whatever the harness runs, so quality is not pinned and not comparable across
installs. Deliveries record ``source`` so that distinction survives into any
later analysis.

Run it with ``halflife-mcp`` (stdio transport).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from mcp.server.mcpserver import MCPServer

from halflife import __version__, extraction, guide
from halflife.db import session_scope
from halflife.extraction import ExtractedSignal
from halflife.generation import engine
from halflife.generation.schemas import GeneratedIssue, PlannedIssue
from halflife.models.base import Feedback, GenerationSource
from halflife.repository import deliveries as delivery_repo
from halflife.repository import series as series_repo
from halflife.repository import subscriptions as subscription_repo
from halflife.shorthand import ShorthandError, parse_shorthand

server = MCPServer(
    name="halflife",
    version=__version__,
    title="HalfLife",
    instructions=(
        "HalfLife keeps professional skills from decaying by delivering short, "
        "depth-controlled reads on a schedule.\n\n"
        "If the user asks what HalfLife is, how to use it, or which depth to "
        "choose, call halflife_help.\n\n"
        "For a new subscription with no plan yet, call halflife_plan_brief and "
        "halflife_record_plan first. A planned series measurably beats an "
        "unplanned one.\n\n"
        "To deliver a due issue: call halflife_list_due, then halflife_next_brief "
        "for a subscription. The brief contains a system prompt and a user prompt. "
        "Follow them exactly — they carry a depth rubric and a coverage ledger of "
        "what earlier issues already established, which must not be explained "
        "again. Write the issue, then call halflife_record_issue with the result. "
        "Do not paraphrase the prompts or substitute your own judgement about "
        "depth: the depth parameter is measured and calibrated.\n\n"
        "If a brief reports needs_compaction, call halflife_compaction_brief and "
        "halflife_record_compaction first, or the series will start losing its "
        "oldest coverage."
    ),
)


def _encode(value: Any) -> str:
    """Datetimes leave as ISO-8601 with an offset, everything else as str.

    `str(datetime)` uses a space separator, which no JSON consumer parses
    without being told to. `isoformat` gives a harness something it can hand
    to its own date library — and the offset is there because the column type
    guarantees an aware value. Issue #4.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _ok(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=_encode)


@server.tool()
def halflife_help() -> str:
    """How HalfLife works: the loop, what to ask for, depths, tools and commands.

    Call this when asked what HalfLife is, how to use it, what depth to choose,
    or what can be done with it. Returns Markdown intended to be shown or
    summarised for the user.
    """
    return guide.guide_text()


@server.tool()
def halflife_list_due() -> str:
    """List subscriptions with an issue due now.

    Returns id, topic, depth, duration and how many issues the series has.
    """
    with session_scope() as session:
        due = subscription_repo.list_due(session)
        return _ok(
            [
                {
                    "subscription_id": s.id,
                    "topic": s.topic,
                    "depth": s.depth,
                    "duration_minutes": s.duration_minutes,
                    "flavour": s.flavour.value,
                    "issues_so_far": s.series.issue_count if s.series else 0,
                }
                for s in due
            ]
        )


@server.tool()
def halflife_list_subscriptions() -> str:
    """List every subscription, due or not, including paused ones."""
    with session_scope() as session:
        return _ok(
            [
                {
                    "subscription_id": s.id,
                    "topic": s.topic,
                    "depth": s.depth,
                    "duration_minutes": s.duration_minutes,
                    "frequency": s.frequency.value,
                    "flavour": s.flavour.value,
                    "status": s.status.value,
                    "next_due_at": s.next_due_at,
                    "issues_so_far": s.series.issue_count if s.series else 0,
                }
                for s in subscription_repo.list_all(session)
            ]
        )


@server.tool()
def halflife_plan_brief(subscription_id: str) -> str:
    """Get the prompt for sketching a series' arc, before writing any issues.

    Worth doing once per new subscription: a planned series measurably beats an
    unplanned one, because without an arc the first issue front-loads material
    that belongs to later ones. Follow the prompts, then call
    halflife_record_plan. Issues can be written without a plan if you skip this.

    Args:
        subscription_id: id from halflife_list_subscriptions, full or a prefix.
    """
    with session_scope() as session:
        subscription = subscription_repo.get_by_prefix(session, subscription_id)
        if subscription is None:
            return _ok({"error": f"no single subscription matches {subscription_id!r}"})

        brief = engine.build_plan_brief(session=session, subscription=subscription)
        return _ok(
            {
                "subscription_id": brief.subscription_id,
                "topic": brief.topic,
                "depth": brief.depth,
                "duration_minutes": brief.duration_minutes,
                "flavour": brief.flavour,
                "issue_count_to_plan": brief.count,
                "already_planned": brief.already_planned,
                "system_prompt": brief.system_prompt,
                "user_prompt": brief.user_prompt,
            }
        )


@server.tool()
def halflife_record_plan(
    subscription_id: str,
    arc_summary: str,
    issues: list[PlannedIssue],
) -> str:
    """Save a series arc you have just drawn up.

    The plan is advisory — later issues may deviate when an open thread matters
    more — so each focus should be specific enough that a future issue can tell
    whether that ground is taken. Replaces any existing plan.

    Args:
        subscription_id: the id from the brief.
        arc_summary: two sentences on where the series starts and ends up.
        issues: the planned issues in order, each with index, title and focus.
    """
    with session_scope() as session:
        subscription = subscription_repo.get_by_prefix(session, subscription_id)
        if subscription is None:
            return _ok({"error": f"no single subscription matches {subscription_id!r}"})
        if not issues:
            return _ok({"error": "issues must not be empty"})

        series = engine.record_plan(
            session=session,
            subscription=subscription,
            arc_summary=arc_summary,
            issues=issues,
        )
        return _ok(
            {
                "topic": subscription.topic,
                "planned_issues": len(series.plan),
                "arc_summary": series.arc_summary,
            }
        )


@server.tool()
def halflife_next_brief(subscription_id: str) -> str:
    """Get everything needed to write the next issue of a series.

    Returns a system_prompt and user_prompt to follow exactly, plus the topic,
    depth and word budget. Write the issue from these, then call
    halflife_record_issue. Check needs_compaction before writing.

    Args:
        subscription_id: id from halflife_list_due, full or a unique prefix.
    """
    with session_scope() as session:
        subscription = subscription_repo.get_by_prefix(session, subscription_id)
        if subscription is None:
            return _ok({"error": f"no single subscription matches {subscription_id!r}"})

        try:
            brief = engine.build_brief(session=session, subscription=subscription)
        except engine.SeriesComplete as exc:
            return _ok({"series_complete": True, "reason": str(exc)})
        return _ok(
            {
                "subscription_id": brief.subscription_id,
                "topic": brief.topic,
                "depth": brief.depth,
                "duration_minutes": brief.duration_minutes,
                "word_budget": brief.word_budget,
                "flavour": brief.flavour,
                "issue_number": brief.issue_number,
                "ledger_size": brief.ledger_size,
                "needs_compaction": brief.needs_compaction,
                "system_prompt": brief.system_prompt,
                "user_prompt": brief.user_prompt,
            }
        )


@server.tool()
def halflife_record_issue(
    subscription_id: str,
    title: str,
    body_markdown: str,
    covered_points_added: list[str],
    open_threads: list[str],
    next_suggested: str,
    plan_index: int = 0,
    model_id: str | None = None,
) -> str:
    """Save an issue you have just written, and advance the series.

    covered_points_added must be short, atomic, self-contained claims — one line
    each, specific enough that a later issue can recognise the ground as covered.
    They are not section headings and not a summary. Pass an empty list for
    open_threads unless the issue deliberately deferred something.

    Args:
        subscription_id: the id from the brief.
        title: issue title, not repeated inside the body.
        body_markdown: the issue itself, Markdown, no title heading.
        covered_points_added: claims this issue established.
        open_threads: things deliberately deferred to a later issue.
        next_suggested: one line on what the next issue should cover.
        plan_index: the series-plan entry this issue covered. 0 if it took an
            open thread or went its own way, which is allowed — an accurate 0
            is worth more than a number chosen to look compliant.
        model_id: the model you ran, if known. Recorded as unknown otherwise.
    """
    with session_scope() as session:
        subscription = subscription_repo.get_by_prefix(session, subscription_id)
        if subscription is None:
            return _ok({"error": f"no single subscription matches {subscription_id!r}"})

        issue = GeneratedIssue(
            title=title,
            body_markdown=body_markdown,
            covered_points_added=covered_points_added,
            open_threads=open_threads,
            next_suggested=next_suggested,
            plan_index=plan_index,
        )
        delivery = engine.record_issue(
            session=session,
            subscription=subscription,
            issue=issue,
            source=GenerationSource.HARNESS,
            model_id=model_id,
        )
        return _ok(
            {
                "delivery_id": delivery.id,
                "issue_number": delivery.issue_number,
                "title": delivery.title,
                "coverage_points_added": len(covered_points_added),
                "plan_index": delivery.plan_index,
                "next_due_at": subscription.next_due_at,
            }
        )


@server.tool()
def halflife_compaction_brief(subscription_id: str) -> str:
    """Get the prompt for compacting a series' oldest coverage entries.

    Only needed when a brief reports needs_compaction. Follow the prompts, then
    call halflife_record_compaction with the merged claims.

    Args:
        subscription_id: the subscription whose ledger needs compacting.
    """
    with session_scope() as session:
        subscription = subscription_repo.get_by_prefix(session, subscription_id)
        if subscription is None:
            return _ok({"error": f"no single subscription matches {subscription_id!r}"})

        brief = engine.build_compaction_brief(session=session, subscription=subscription)
        if brief is None:
            return _ok({"nothing_to_compact": True})
        return _ok(
            {
                "subscription_id": brief.subscription_id,
                "topic": brief.topic,
                "entry_count": brief.entry_count,
                "target": brief.target,
                "system_prompt": brief.system_prompt,
                "user_prompt": brief.user_prompt,
            }
        )


@server.tool()
def halflife_record_compaction(subscription_id: str, claims: list[str]) -> str:
    """Save merged claims, replacing the oldest coverage entries.

    The originals are kept and marked, never deleted.

    Args:
        subscription_id: the subscription being compacted.
        claims: merged claims, each specific enough to recognise ground by.
    """
    with session_scope() as session:
        subscription = subscription_repo.get_by_prefix(session, subscription_id)
        if subscription is None:
            return _ok({"error": f"no single subscription matches {subscription_id!r}"})

        summaries = engine.record_compaction(
            session=session, subscription=subscription, claims=claims
        )
        series = series_repo.get_for_subscription(session, subscription.id)
        active = len(series_repo.coverage_points(session, series.id, active_only=True))
        return _ok({"summaries_written": len(summaries), "active_ledger_size": active})


@server.tool()
def halflife_pending_reads() -> str:
    """Issues that have been written but not yet read.

    Call this at the start of a session to see what is waiting.
    """
    with session_scope() as session:
        return _ok(
            [
                {
                    "delivery_id": d.id,
                    "title": d.title,
                    "topic": d.subscription.topic,
                    "issue_number": d.issue_number,
                    "depth": d.depth,
                    "duration_minutes": d.duration_minutes,
                }
                for d in delivery_repo.list_unacknowledged(session)
            ]
        )


@server.tool()
def halflife_read(delivery_id: str) -> str:
    """Fetch an issue's full text and mark it read.

    Args:
        delivery_id: id from halflife_pending_reads, full or a unique prefix.
    """
    with session_scope() as session:
        delivery = delivery_repo.get_by_prefix(session, delivery_id)
        if delivery is None:
            return _ok({"error": f"no single delivery matches {delivery_id!r}"})
        delivery_repo.mark_fetched(session, delivery)
        return _ok(
            {
                "delivery_id": delivery.id,
                "title": delivery.title,
                "topic": delivery.subscription.topic,
                "issue_number": delivery.issue_number,
                "depth": delivery.depth,
                "body_markdown": delivery.body_markdown,
            }
        )


@server.tool()
def halflife_feedback(delivery_id: str, verdict: str) -> str:
    """Record feedback on an issue.

    Two axes. too_basic and too_advanced are about the level, and move the
    subscription's depth. already_knew and wrong_subject are about the subject:
    the level was fine and the ground was wrong. Those leave depth alone and are
    shown to the next few generations, which are told to go elsewhere.

    Args:
        delivery_id: the issue being rated.
        verdict: too_basic, just_right, too_advanced, already_knew, or wrong_subject.
    """
    normalised = verdict.strip().lower().replace("-", "_")
    try:
        parsed = Feedback(normalised)
    except ValueError:
        return _ok(
            {
                "error": "verdict must be one of: too_basic, just_right, "
                "too_advanced, already_knew, wrong_subject"
            }
        )

    with session_scope() as session:
        delivery = delivery_repo.get_by_prefix(session, delivery_id)
        if delivery is None:
            return _ok({"error": f"no single delivery matches {delivery_id!r}"})

        delivery_repo.set_feedback(session, delivery, parsed)
        subscription = delivery.subscription
        before = subscription.depth
        after = subscription_repo.apply_feedback_to_depth(session, subscription, parsed)
        return _ok(
            {
                "topic": subscription.topic,
                "axis": "depth" if parsed.is_about_depth else "subject",
                "depth_before": before,
                "depth_now": after,
            }
        )


@server.tool()
def halflife_subscribe(spec: str) -> str:
    """Create a subscription from shorthand: topic, depth, duration, frequency, flavour.

    Everything after the topic is optional. Depth is 1-5, duration is minutes,
    frequency is 1h/1d/1w, flavour is learning or maintaining. The series has no
    plan until one is generated; issues can be written without one.

    Args:
        spec: e.g. "sap web dispatcher, 4, 5, 1d"
    """
    try:
        parsed = parse_shorthand(spec)
    except ShorthandError as exc:
        return _ok({"error": str(exc)})

    with session_scope() as session:
        subscription = subscription_repo.create(session, parsed)
        engine.ensure_series(session, subscription)
        return _ok(
            {
                "subscription_id": subscription.id,
                "topic": subscription.topic,
                "depth": subscription.depth,
                "duration_minutes": subscription.duration_minutes,
                "frequency": subscription.frequency.value,
                "flavour": subscription.flavour.value,
            }
        )


@server.tool()
def halflife_add_thread(subscription_id: str, thread: str) -> str:
    """Tell a series it missed something the reader wants covered.

    Use this when the reader says the series left out a subject, or names
    something it should cover next. The next issue is shown it and told it
    outranks the series plan.

    Advisory rather than a queue: a generator that takes the subject clears the
    thread, and one that judges it not worth an issue drops it. Do not promise
    the reader it will definitely appear.

    This says what to write about and never at what level. Depth is moved by
    halflife_feedback, not here.

    Args:
        subscription_id: the series that missed it, full id or a unique prefix.
        thread: what it should cover, in the reader's terms.
    """
    with session_scope() as session:
        subscription = subscription_repo.get_by_prefix(session, subscription_id)
        if subscription is None:
            return _ok({"error": f"no single subscription matches {subscription_id!r}"})

        state = series_repo.get_for_subscription(session, subscription.id)
        if state is None:
            return _ok({"error": "that subscription has no series yet; write an issue first"})

        threads = series_repo.add_thread(session, state, thread)
        return _ok(
            {
                "topic": subscription.topic,
                "open_threads": len(threads),
                "note": "Advisory. The next issue is told it outranks the plan, and may still "
                        "judge it not worth an issue.",
            }
        )


@server.tool()
def halflife_extraction_brief() -> str:
    """Get the prompt for classifying the session you are in, when the user asks.

    Call this only when the user asks for their session to be logged. Nothing
    here runs on its own, and nothing should be recorded without them asking.

    Returns a system prompt and a user prompt to follow exactly, plus the
    vocabularies the classification must use. Follow them, then call
    halflife_record_signals with the result — or call nothing, if the session
    produced nothing worth recording, which is a normal outcome.

    You classify the conversation yourself. The conversation is never sent
    anywhere: what goes back are subject names and behavioural verbs, and there
    is no field in which anything else could travel.
    """
    brief = extraction.build_extraction_brief()
    return _ok(
        {
            "system_prompt": brief.system_prompt,
            "user_prompt": brief.user_prompt,
            "extraction_prompt_version": brief.prompt_version,
            "signal_types": brief.signal_types,
            "confidence_levels": brief.confidence_levels,
            "context_categories": brief.context_categories,
        }
    )


@server.tool()
def halflife_record_signals(
    signals: list[ExtractedSignal],
    session_key: str,
    harness: str,
    agent_version: str = "unknown",
) -> str:
    """Save the classifications from halflife_extraction_brief.

    Each signal is topics, signal_type, confidence and context_category, and
    nothing else — no excerpts, no summaries, no identifiers. Send an empty
    list, or do not call this at all, if the session produced nothing.

    Args:
        signals: the classifications, following the brief exactly.
        session_key: any stable string identifying this session. It is hashed
            on arrival and the hash is what is stored, so that two signals from
            one sitting can be seen as related without the sitting being
            identifiable. The value you pass is never stored or logged.
        harness: which tool you are, e.g. "claude-code".
        agent_version: your version, if you know it.
    """
    with session_scope() as session:
        rows = extraction.record_signals(
            session=session,
            signals=signals,
            session_key=session_key,
            harness=harness,
            agent_version=agent_version,
        )
        return _ok(
            {
                "recorded": len(rows),
                "extraction_prompt_version": rows[0].extraction_prompt_version if rows else None,
                "note": "Signals are write-only. There is no read path for individual signals.",
            }
        )


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
