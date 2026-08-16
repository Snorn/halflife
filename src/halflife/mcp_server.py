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
from typing import Any

from mcp.server.mcpserver import MCPServer

from halflife import __version__
from halflife.db import session_scope
from halflife.generation import engine
from halflife.generation.schemas import GeneratedIssue
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


def _ok(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=str)


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

        brief = engine.build_brief(session=session, subscription=subscription)
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
                for d in delivery_repo.list_unread(session)
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
        delivery_repo.mark_read(session, delivery)
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
    """Record whether an issue was pitched right, adjusting future depth.

    Args:
        delivery_id: the issue being rated.
        verdict: too_basic, just_right, or too_advanced.
    """
    normalised = verdict.strip().lower().replace("-", "_")
    try:
        parsed = Feedback(normalised)
    except ValueError:
        return _ok(
            {"error": "verdict must be one of: too_basic, just_right, too_advanced"}
        )

    with session_scope() as session:
        delivery = delivery_repo.get_by_prefix(session, delivery_id)
        if delivery is None:
            return _ok({"error": f"no single delivery matches {delivery_id!r}"})

        delivery_repo.set_feedback(session, delivery, parsed)
        subscription = delivery.subscription
        before = subscription.depth
        after = subscription_repo.apply_feedback_to_depth(session, subscription, parsed)
        return _ok({"topic": subscription.topic, "depth_before": before, "depth_now": after})


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


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
