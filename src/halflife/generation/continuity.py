"""Series continuity: rendering the state into the prompt, and folding a new
issue's output back into it.

The coverage ledger is fed to every generation in full, up to
``MAX_LEDGER_POINTS``. Beyond that the oldest points are elided and the prompt
says so. At roughly five points per issue that is about forty issues before any
elision happens; when a series outlives that, the honest fix is summarising old
points rather than silently dropping them, which is deferred.
"""

from __future__ import annotations

from typing import Any

from halflife.generation.schemas import GeneratedIssue
from halflife.models.base import new_id
from halflife.models.series import CoveragePoint, Series

MAX_LEDGER_POINTS = 200


def render_plan_block(
    plan: list[dict[str, Any]], arc_summary: str, issue_number: int
) -> str:
    if not plan:
        return "Series plan: none — this is an unplanned series. Choose the subject yourself."

    lines = ["Series plan (advisory):"]
    if arc_summary:
        lines.append(f"  Arc: {arc_summary}")
    for entry in plan:
        index = entry.get("index")
        marker = "->" if index == issue_number else "  "
        status = " [already written]" if isinstance(index, int) and index < issue_number else ""
        lines.append(f"  {marker} {index}. {entry.get('title', '')} — {entry.get('focus', '')}{status}")
    return "\n".join(lines)


def render_ledger_block(points: list[str]) -> str:
    if not points:
        return "Coverage ledger: empty — this is the first issue. Nothing has been covered yet."

    shown = points[-MAX_LEDGER_POINTS:]
    elided = len(points) - len(shown)
    header = "Coverage ledger — already established, do NOT explain any of this again:"
    if elided:
        header += f"\n  (the {elided} oldest points are omitted for length)"
    lines = [header]
    lines.extend(f"  - {point}" for point in shown)
    return "\n".join(lines)


def render_threads_block(threads: list[str]) -> str:
    if not threads:
        return "Open threads: none."
    lines = ["Open threads — a previous issue deferred these. Pick one up or drop it:"]
    lines.extend(f"  - {t}" for t in threads)
    return "\n".join(lines)


def apply_issue(
    *,
    series: Series,
    issue: GeneratedIssue,
    delivery_id: str,
    tenant_id: str,
) -> list[CoveragePoint]:
    """Fold a generated issue back into the series state.

    Returns the new coverage rows; the caller adds them to the session.
    """
    start = len(series.coverage)
    new_points = [
        CoveragePoint(
            id=new_id(),
            tenant_id=tenant_id,
            series_id=series.id,
            delivery_id=delivery_id,
            position=start + offset,
            point=text.strip(),
        )
        for offset, text in enumerate(issue.covered_points_added)
        if text.strip()
    ]
    series.coverage.extend(new_points)
    series.open_threads = [t.strip() for t in issue.open_threads if t.strip()]
    series.issue_count = max(series.issue_count, 0) + 1
    return new_points


def plan_to_json(plan_issues: list[Any]) -> list[dict[str, Any]]:
    return [
        {"index": p.index, "title": p.title, "focus": p.focus}
        for p in plan_issues
    ]
