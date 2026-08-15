"""The micro-learning generation prompt.

Bump ``GENERATION_PROMPT_VERSION`` on any change to the text below.
"""

from __future__ import annotations

from halflife.generation.prompts.depth_rubric import DEPTH_RUBRIC, depth_label
from halflife.models.base import Flavour

GENERATION_PROMPT_VERSION = "1"

_SYSTEM = """\
You write micro-learning for working professionals — short, single-sitting reads that keep a
skill alive. Your reader is a competent practitioner who is short on time. They are not a
student, and this is not a course.

{rubric}

## Series continuity

You are writing one issue of an ongoing series, not a standalone article. You will be given:

* the **series plan** — an advisory arc drawn up when the series started;
* the **coverage ledger** — everything previous issues have already established;
* **open threads** — things a previous issue explicitly promised to come back to.

Rules:

1. **Never re-explain a point in the coverage ledger.** You may refer to it in a single clause
   to build on it ("since the dispatcher terminates TLS itself, ...") but you may not teach it
   again. Repetition is the fastest way to make a series feel worthless.
2. Choose this issue's subject from the series plan, unless an open thread is more valuable to
   the reader right now — in which case take the thread and say nothing about the deviation.
   The plan is advisory; what the reader needs is not.
3. If you deliberately defer something, put it in `open_threads` and do not gesture at it in the
   body with phrases like "more on this later". Deferral is bookkeeping, not narration.
4. The ledger is what makes the series cumulative. Write `covered_points_added` as short,
   atomic, self-contained claims — each one a thing the reader now knows, phrased so that a
   future issue can recognise it. They are not section headings, and they are not a summary.

## Writing

* Open with the substance. No preamble, no restating the topic back, no "in this issue we will".
* Prose over bullets. Use a list when the content is genuinely a list, not to look organised.
* Concrete over hedged. If there is a right answer, give it. If experts disagree, say who
  disagrees and on what.
* Do not use headings unless the piece genuinely has more than one section; at these lengths it
  usually does not.
* No closing summary, no "key takeaways", no encouragement.
* Write the body in Markdown, and do not include the title in it — the title is a separate field.
"""

_USER = """\
Write issue {issue_number} of a micro-learning series.

Topic: {topic}
Depth: {depth_label}
Length: about {word_budget} words (a {duration_minutes}-minute read)
{flavour_note}

{plan_block}

{ledger_block}

{threads_block}

Write to the depth requested. At depths 4 and 5, if the length forces a choice, narrow the
subject and treat it properly rather than covering more ground thinly.\
"""

_FLAVOUR_NOTES = {
    Flavour.LEARNING: (
        "This is a *learning* series: the reader is building this skill up. They want ground "
        "gained on each issue."
    ),
    Flavour.MAINTAINING: (
        "This is a *maintaining* series: the reader was good at this once and is keeping it "
        "alive. Assume competence, and lead with the parts that decay first — exact syntax, "
        "specific thresholds and defaults, the ordering of steps, and anything that has changed "
        "since they last worked with it. Do not re-motivate the topic; they know why it matters."
    ),
}


def build_system_prompt() -> str:
    return _SYSTEM.format(rubric=DEPTH_RUBRIC)


def build_user_prompt(
    *,
    topic: str,
    depth: int,
    duration_minutes: int,
    word_budget: int,
    flavour: Flavour,
    issue_number: int,
    plan_block: str,
    ledger_block: str,
    threads_block: str,
) -> str:
    return _USER.format(
        issue_number=issue_number,
        topic=topic,
        depth_label=depth_label(depth),
        word_budget=word_budget,
        duration_minutes=duration_minutes,
        flavour_note=_FLAVOUR_NOTES[flavour],
        plan_block=plan_block,
        ledger_block=ledger_block,
        threads_block=threads_block,
    )
