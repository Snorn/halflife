"""The one-shot series arc, drawn up when a subscription is created.

Advisory only — generation may deviate when an open thread is more valuable.
Its job is to stop the series random-walking around the topic.
"""

from __future__ import annotations

from halflife.generation.prompts.depth_rubric import DEPTH_RUBRIC, depth_label
from halflife.models.base import Flavour

SERIES_PLAN_PROMPT_VERSION = "1"

_SYSTEM = """\
You plan micro-learning series for working professionals. A series is a sequence of short,
single-sitting reads on one topic, delivered on a schedule.

{rubric}

A good plan has an arc: each issue should be usable on its own, but the sequence should build,
so that issue 6 can assume issues 1 to 5. Order by dependency first and by usefulness second —
put the thing the reader most needs early, unless it depends on something else.

The plan is advisory. Do not try to be exhaustive about the topic; be deliberate about the
first {count} issues at the requested depth.
"""

_USER = """\
Plan a {count}-issue micro-learning series.

Topic: {topic}
Depth: {depth_label}
Each issue: about a {duration_minutes}-minute read
{flavour_note}

For each issue give a title and a one-sentence `focus` describing what that issue establishes —
specific enough that a later issue can tell whether the ground has been covered. Also write a
two-sentence `arc_summary` describing where the series starts and where it gets to.

Pitch every issue at the requested depth. A depth-5 series does not open with a depth-1
introduction.\
"""

_FLAVOUR_NOTES = {
    Flavour.LEARNING: "The reader is building this skill up from where they are now.",
    Flavour.MAINTAINING: (
        "The reader was good at this once and is keeping it alive. Weight the plan toward what "
        "decays first — exact syntax, specific defaults and thresholds, step ordering, and what "
        "has changed recently — rather than fundamentals they still hold."
    ),
}


def build_system_prompt(*, count: int) -> str:
    return _SYSTEM.format(rubric=DEPTH_RUBRIC, count=count)


def build_user_prompt(
    *,
    topic: str,
    depth: int,
    duration_minutes: int,
    flavour: Flavour,
    count: int,
) -> str:
    return _USER.format(
        count=count,
        topic=topic,
        depth_label=depth_label(depth),
        duration_minutes=duration_minutes,
        flavour_note=_FLAVOUR_NOTES[flavour],
    )
