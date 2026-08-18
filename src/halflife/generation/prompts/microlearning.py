"""The micro-learning generation prompt.

Bump ``GENERATION_PROMPT_VERSION`` on any change to the text below.

v2 responds to two of three continuity runs failing the same way: the last
issue re-explained a mechanism the first had established — the admission
pipeline order on one topic, per-dispatcher load counters on another. Both
times the new coverage points were genuinely novel, so the ledger's
near-duplicate check saw nothing; only the prose repeated.

v1 already said not to re-explain, and was ignored, in the same way the depth
rubric's abstract depth-5 description was ignored until it was given a
concrete test. So v2 names the situation where the rule actually breaks — a
ledger point that is a *premise* for the current subject — states the
compression to apply, and adds a closing scan, which is the pattern that
worked for the depth rubric's calibration checks.

Caveat on that reasoning, recorded because it would otherwise be read as a
success story: those failures were mostly the eval's own overlap judge
misfiring. It returned a boolean and quoted fragments, and was flagging
correct cumulative writing — "safe to retry because nothing has been sent to
the client yet" is the exact clause form this prompt prescribes — as
re-explanation. Once the judge was made to quote whole sentences and separate
a reference from a restatement, both previously failing topics came back with
41 references and zero restatements across six checks.

v3 adds two rules and one input block, neither of them measured yet.

The first is the callback rule. Nothing in v1 or v2 said which ledger point to
build on, and the nearest one is the easiest to reach for, so a series drifts
towards referring only to last week. Reaching further back is what makes the
reader retrieve something rather than recognise it, which is the whole reason
this is a series and not a pile of articles. The rule is deliberately hedged
against manufacture: an invented connection is worse than no callback.

The second is reader feedback on the subject axis. `already_knew` and
`wrong_subject` are new verbs that leave depth alone, so unlike the depth verbs
they have nowhere to go except the prompt. The rule says so explicitly, and
tells the generator not to compensate for depth feedback, which it can see the
effect of but not the cause.

The plan block carries the same signal structurally: an entry the reader
rejected is marked in place, so it stays struck out for the life of the series
rather than only for the few issues the prose list covers. That marking is
positional — the plan is advisory, and an issue that took an open thread
instead breaks the correspondence — which `render_plan_block` documents. The
existing "already written" marker has always made the same assumption.

All three are the same shape as the v2 change — name the situation, state what
to do — and carry the same caveat. None has been run against a judge.

So v2 is not a proven improvement over v1. Its guidance stands on its own
merits, but the evidence that motivated it was an instrument fault, and if
anyone wants to know whether v1 was fine, the way to find out is to run both
against the current judge rather than to assume this one is better.
"""

from __future__ import annotations

from halflife.generation.prompts.depth_rubric import DEPTH_RUBRIC, depth_label
from halflife.models.base import Flavour

GENERATION_PROMPT_VERSION = "3"

_SYSTEM = """\
You write micro-learning for working professionals — short, single-sitting reads that keep a
skill alive. Your reader is a competent practitioner who is short on time. They are not a
student, and this is not a course.

{rubric}

## Series continuity

You are writing one issue of an ongoing series, not a standalone article. You will be given:

* the **series plan** — an advisory arc drawn up when the series started;
* the **coverage ledger** — everything previous issues have already established;
* **open threads** — things a previous issue explicitly promised to come back to;
* **reader feedback** — what the reader said about recent issues, where they said anything.

Rules:

1. **Never re-explain a point in the coverage ledger.** You may refer to it in a single clause
   to build on it ("since the dispatcher terminates TLS itself, ...") but you may not teach it
   again. Repetition is the fastest way to make a series feel worthless.

   This bites hardest when a ledger point is a **premise** for what you are writing now — the
   mechanism your subject depends on. That is exactly where the rule gets broken, because
   restating it feels like being helpful. Compress it to one subordinate clause and move on:
   never a paragraph, never a walkthrough, never a restated sequence of steps. The test to
   apply: if a passage would teach a ledger point to somebody who had **not** read the earlier
   issue, that passage is the bug. Assume your reader has read every issue, because they have.
2. Choose this issue's subject from the series plan, unless an open thread is more valuable to
   the reader right now — in which case take the thread and say nothing about the deviation.
   The plan is advisory; what the reader needs is not.
3. If you deliberately defer something, put it in `open_threads` and do not gesture at it in the
   body with phrases like "more on this later". Deferral is bookkeeping, not narration.
4. **Reach back, not only one step.** Where a ledger point is worth building on and both an
   older and a recent one would serve, prefer the older. A reader recalls something by having
   to use it, so a callback across several issues is worth more to them than one to the issue
   they read yesterday. Do not manufacture these: only where the connection is real.
5. **Reader feedback outranks the plan.** If the reader said they already knew an issue's
   material, do not spend another issue near that ground — go somewhere they have not been. If
   they said an issue was not what they needed, the plan is wrong about what matters on this
   topic; take a different line through it. Rejected entries are marked in the plan block —
   treat those as struck out, not as ground to cover better. Feedback about depth has already
   been applied to the depth parameter you were given, so do not compensate for it again.
6. The ledger is what makes the series cumulative. Write `covered_points_added` as short,
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

## Before you answer

Scan the draft for any passage that explains something already in the coverage ledger, and
replace each one with a clause. The usual offender is a paragraph near the top that sets up the
mechanism you are about to build on — the reader already has that mechanism, which is why it is
in the ledger.
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

{feedback_block}

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
    feedback_block: str = "",
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
        feedback_block=feedback_block,
    )
