"""Series continuity: rendering the state into the prompt, and folding a new
issue's output back into it.

The coverage ledger is fed to every generation in full, up to
``MAX_LEDGER_POINTS``. Beyond that the oldest points are elided and the prompt
says so.

Measured, not guessed: the first continuity eval produced 79 points across 6
issues at depth 4 — about 13 per issue, not the 5 this cap was originally sized
against. Elision therefore begins around issue 15, roughly two weeks of daily
delivery, rather than the forty issues assumed here before. Raising the cap only
moves the wall (a year of daily issues would be some 4,800 points, far past what
is worth putting in a prompt), so the real fix is summarising displaced points
into durable claims rather than dropping them. That work is still deferred, but
it lands in weeks rather than months and should be scheduled accordingly.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from halflife.generation.schemas import GeneratedIssue
from halflife.models.base import CoverageKind, new_id, utcnow
from halflife.models.series import CoveragePoint, Series

# The most entries that go into a prompt. Compaction keeps the active ledger
# under this, so the truncation path in render_ledger_block is now a backstop
# for a series that somehow outran compaction rather than the normal case.
MAX_LEDGER_POINTS = 200

# Compact once the active ledger reaches the cap, folding the oldest slice into
# roughly a quarter as many claims. At ~13 points an issue that is a compaction
# every five or six issues once a series is past its second week.
COMPACT_TRIGGER = MAX_LEDGER_POINTS
COMPACT_OLDEST = 80
COMPACT_RATIO = 4

# How many subject-feedback entries are spelled out in full. The plan block
# marks every rejected entry regardless; this only bounds the prose list.
FEEDBACK_SHOWN = 3

_REJECTION_NOTES = {
    "already_knew": "the reader already knew this, so do not return to it",
    "wrong_subject": "the reader said this was not what they needed, so take a different line",
}


def render_plan_block(
    plan: list[dict[str, Any]],
    arc_summary: str,
    issue_number: int,
    written: set[int] | None = None,
    rejected: dict[int, str] | None = None,
) -> str:
    """Render the advisory arc, marking what has been written and what missed.

    ``written`` and ``rejected`` are keyed by plan entry number, taken from what
    each generation reported it covered rather than inferred from its position
    in the series. An entry the plan lists but nothing ever took stays unmarked,
    which is the point: the series skipping an entry and covering it are
    different facts, and position cannot tell them apart.

    ``written`` defaults to the old positional rule so the function still reads
    sensibly on its own; callers with the deliveries to hand should pass it.
    """
    if not plan:
        return "Series plan: none — this is an unplanned series. Choose the subject yourself."

    rejected = rejected or {}
    lines = ["Series plan (advisory):"]
    if arc_summary:
        lines.append(f"  Arc: {arc_summary}")
    for entry in plan:
        index = entry.get("index")
        marker = "->" if index == issue_number else "  "
        was_written = (
            index < issue_number if written is None else index in written
        )
        status = ""
        if isinstance(index, int) and was_written:
            note = _REJECTION_NOTES.get(rejected.get(index, ""))
            status = f" [already written; {note}]" if note else " [already written]"
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


def render_feedback_block(entries: Sequence[tuple[int, str, str, Any]]) -> str:
    """Recent *subject* feedback, as (issue number, title, verdict, ...).

    Depth feedback is deliberately excluded: it has already moved the depth
    parameter, and showing it here would invite the generator to correct for it
    a second time.
    """
    if not entries:
        return "Reader feedback: none so far."

    entries = entries[-FEEDBACK_SHOWN:]

    labels = {
        "already_knew": "already knew this material",
        "wrong_subject": "this was not what they needed",
    }
    lines = ["Reader feedback on recent issues — let this override the plan:"]
    lines.extend(
        f"  - issue {entry[0]} ({entry[1]}): {labels.get(entry[2], entry[2])}"
        for entry in entries
    )
    return "\n".join(lines)


_READER_PREFIX = "Asked for by the reader:"


def render_threads_block(threads: list[str]) -> str:
    if not threads:
        return "Open threads: none."
    reader = [t for t in threads if t.startswith(_READER_PREFIX)]
    header = "Open threads — a previous issue deferred these. Pick one up or drop it:"
    if reader:
        header = (
            "Open threads. Ones marked as asked for by the reader outrank the plan — they are "
            "the reader saying the series missed something, which they are better placed to "
            "judge than the plan is. The rest a previous issue deferred; pick one up or drop it:"
        )
    lines = [header]
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
    # Positions must keep climbing. Compaction inserts summaries at the low
    # positions they replace, so the count of rows is not the next position.
    start = max((p.position for p in series.coverage), default=-1) + 1
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


def active_points(series: Series) -> list[CoveragePoint]:
    """Ledger rows still shown to the generator, oldest first."""
    return sorted(
        (p for p in series.coverage if p.compacted_at is None),
        key=lambda p: p.position,
    )


def needs_compaction(series: Series) -> bool:
    return len(active_points(series)) >= COMPACT_TRIGGER


def points_to_compact(series: Series) -> list[CoveragePoint]:
    """The oldest slice, or nothing at all if the ledger does not need folding.

    Summaries are ordinary ledger rows, so a long-running series compacts its
    own summaries rather than accumulating an ever-growing tier of them. That
    is also why the trigger is checked *here* rather than left to callers:
    compaction is lossy and irreversible, and a second pass over a ledger that
    did not need one folds the summaries written by the first, losing detail
    each time.

    Every route in — the API path, the harness brief, and the MCP tool a model
    may call whenever it likes — goes through this function, so the precondition
    holds without three callers each remembering to check it.
    """
    if not needs_compaction(series):
        return []
    return active_points(series)[:COMPACT_OLDEST]


def compaction_target(count: int) -> int:
    return max(1, count // COMPACT_RATIO)


def apply_compaction(
    *,
    series: Series,
    replaced: list[CoveragePoint],
    claims: list[str],
    tenant_id: str,
) -> list[CoveragePoint]:
    """Fold ``replaced`` into ``claims``, without deleting anything.

    The summaries take the position of the oldest row they replace, so ledger
    order survives compaction and the prompt still reads chronologically.
    """
    kept = [text.strip() for text in claims if text.strip()]
    if not kept or not replaced:
        return []

    at = utcnow()
    base = min(p.position for p in replaced)
    for point in replaced:
        point.compacted_at = at

    summaries = [
        CoveragePoint(
            id=new_id(),
            tenant_id=tenant_id,
            series_id=series.id,
            delivery_id=None,
            position=base + offset,
            point=text,
            kind=CoverageKind.SUMMARY,
        )
        for offset, text in enumerate(kept)
    ]
    series.coverage.extend(summaries)
    return summaries


def plan_to_json(plan_issues: list[Any]) -> list[dict[str, Any]]:
    return [
        {"index": p.index, "title": p.title, "focus": p.focus}
        for p in plan_issues
    ]
