"""Ledger-to-questions: can a coverage point become a question worth failing?

This is the cheapest real test of the Geiger decision recorded on 2026-08-24 —
that Geiger is a sensor feeding HalfLife rather than a second head on a shared
core. That decision rests on two claims, and this experiment attacks both:

1. **A ledger point is enough to write a discriminating item from.** If it is,
   Geiger needs no separate content pipeline: HalfLife's own ledger is the
   question bank, and the calibrated depth rubric does double duty.
2. **A wrong answer names a subscription you would actually want.** If the
   suggestion is a topic you would not have chosen, the pipeline emits noise,
   and the honest conclusion is that Geiger needs its own subject model.

Nothing here is Geiger. It writes no signals, creates no subscriptions, and
adds no tables — it reads the live ledger, calls the API, prints, and stops.
Building Geiger means deciding all the things this deliberately does not:
where items live, how they are scheduled, what a session is. Do not grow this
file into that. If the result is good, the next artefact is a decision record,
not more of this script.

    .venv/Scripts/python evals/geiger_probe.py --list
    .venv/Scripts/python evals/geiger_probe.py 9917e7f5 --items 10 --dry-run
    .venv/Scripts/python evals/geiger_probe.py 9917e7f5 --items 10

``--dry-run`` writes and screens the items but does not ask you to sit the
test. Run it first: item quality is the cheaper of the two claims to falsify,
and if the items are bad, your score would not mean anything anyway.

Generating and sitting can also be separated, which is what ``--score`` is for
and is the better test — a paper sat a week after it was written measures decay
rather than short-term recall:

    .venv/Scripts/python evals/geiger_probe.py --score evals/output/<file>.json \
        --answers BDACBACDBA

Screening deliberately withholds the blind control's notes, because they name
the option they are about and ``--dry-run`` is the mode you run *before* sitting
the paper. Seven of ten answers went up on screen that way once. ``--reveal``
prints them anyway, for a paper nobody is going to sit.

## What this can and cannot show

The reason it needs saying up front is that the obvious version of this
experiment measures the wrong thing.

**The circularity.** The model that wrote the issue also writes the question.
Ask it to write an item *about the ledger point* and you measure whether the
reader retained a claim HalfLife made — which comes apart from whether the
reader knows the subject exactly when HalfLife was wrong. The item prompt
therefore asks for a question about the underlying subject, answerable by
someone who learned it elsewhere, and forbids referring to the series. That
narrows the gap. It does not close it, because the subject the model reaches
for is still the one it chose to write about.

**The blind control.** Every item is attempted by a second call that has never
seen the ledger point, and which reports whether it *knew* the answer,
*eliminated* its way there, or *guessed*. Two different faults show up here.
An item eliminated or guessed correctly has bad distractors and measures
test-craft. An item genuinely known cold is a fair question about the field,
but it is not measuring the decay of this series — a well-read generalist
would pass it without ever having read an issue. Both are reported; only the
first is a defect.

Read that second number with the topic in mind. The generalist here is a model,
and on subjects it is unusually expert in — the Claude API above all — it will
know essentially every item cold, so the count stops discriminating and says
more about the proxy than the paper.

**The form judge.** A third call, which never answers the item, is shown only
the wording and asked which option stands out: longest, most hedged, most
specific, the one that reads like a textbook. It may answer that none does, and
for a well-built item that is the expected answer.

This used to be a field on the blind control, and it was wrong to put it there.
One call that answers the item and then reports whether the answer was
signposted will reason from truth to form: it worked out which option was true
and described that one as the standout, firing on 93% of items where this judge
finds 59%, and on 100% of a set that had just been fixed. Separation is not
tidiness. It is the only reason the number can be believed, so do not fold the
two calls back together to save a call.

The judge distinguishes two faults that are not the same. A standout that *is*
the key hands the answer over, which inflates a score — so a low score on such
items is a floor on decay rather than an artefact. A standout that is *not* the
key is worse: it drags the reader toward a wrong answer, manufacturing failures
rather than hiding them, and a pipeline built on those would prescribe
refreshers for decay that never happened.

**What is left uncontrolled.** You are one rater, you curated the rubric these
items are written against, and you know you are being tested on material you
chose to subscribe to. Ten items is not a measurement, it is a look. The point
of running it is to find out whether the idea survives contact at all, which
is a question ten items can answer in the negative and cannot answer in the
affirmative.

## What the first runs found — 2026-08-24, rubric v6, item prompt v1

Nine items across three runs on the SAP Autonomous Enterprise ledger, dry-run
only. Two faults, one fixed and one not, and the unfixed one is the finding.

**Position bias — fixed.** The first three items were keyed A, A, A. Left to
itself the model writes the true claim first and pads three distractors after
it. The answer slot is now assigned by the caller, round-robin and shuffled,
which removed it outright: the next run keyed ABCD. This was never going to
yield to better wording, because each item is a separate call that cannot see
where the others put their answers.

**The correct option signals itself — not fixed, and it is the result.** The
blind control flagged a tell in every item of every run. Tightening the prompt
moved what the tell *was* without removing it. Before: the true option was the
longest and most hedged while the distractors were strawmen. After an explicit
length-and-hedging parity rule, and distractors required to be claims someone
has actually held: the true option became the only one with a reason clause,
the only one with a two-part structure, the only one framed the way a textbook
frames it. The model cannot argue for a claim it believes without the argument
showing, and the shape of the argument is visible to a reader who knows nothing
about the subject.

That matters for the Geiger decision rather than for this script. It says
one-shot item generation from a ledger point does not produce an instrument
that measures decay, and the honest readings are: distractors need to be
written by something that is not trying to be right — a separate adversarial
pass, or drawn from the reader's own wrong answers — or the format is wrong and
the item should be free response scored against the point, where there is no
option set to leak through. Either is a real piece of work, and it lands on the
Geiger side of the boundary, not here.

**The tell detector was uncalibrated, and has now been calibrated.** It is the
same model, and a detector asked whether a tell exists has every reason to find
one — nine for nine fits an over-firing detector as well as it fits bad items.
The plan was to compare against items from a real certification exam. That was
dropped: it means reproducing published exam content into this repository, and
there is a sharper test that needs no outside material. Run ``--calibrate`` over
saved runs.

## What the calibration found — 2026-08-24, 32 items pooled from six runs

**The key is measurably the longest option, 25 times in 32 (78%, chance 25%).**
No model is involved in that number — it counts characters. The length tell the
item prompt forbids in as many words is simply present, and the prompt revision
that was supposed to remove it did not.

**A form-only judge, never shown the key, picks it 19 times in 32 (59%, chance
25%).** It is asked which option stands out by how it is written and is allowed
to answer that none does, which it did 13 times. The conditional rate is the
striking one: **of the 19 items where form alone singles an option out, the
option it singles out is the correct one 19 times out of 19.** When these items
leak they leak completely.

**The detector over-fires, so its own rate was wrong.** It reported a tell in 25
of 27 (93%) where the stricter form judge finds one in 59%. "Ten out of ten" was
inflated; about two items in five are clean. Both facts survive: the leak is
real, and the detector overstates how much of it there is.

**The direction matters more than the rate.** A tell points *at* the correct
answer, so it can only push a score up. A reader who scores badly on leaky items
scored badly with help, which makes a low score a floor on decay rather than an
artefact of bad items. This inverts the obvious reading, and the obvious reading
was in this file until the controls were run.

The form judge is not truly blind — a strong model cannot unsee which option is
true, and its agreement is an upper bound. That is why disagreement would have
been the decisive outcome: the confound can manufacture agreement and cannot
manufacture chance. Control 1 has no such weakness and points the same way.

## The attention control — set up 2026-08-25, reads out 2026-08-27

The first sitting found 3 of 8 retained on `6a2ead85` at roughly 39-51 hours,
and the obvious reading — that the reader's capacity or the volume per issue is
the problem — has a competitor that costs nothing to exclude. Both baseline
issues were read inside sessions where the reader was also building this
repository. Reading while doing something else is a different act from reading
attentively, and it has a different fix: delivery context, not a depth scale.

So: issue 3 of the same series, same path, same depth 3, same five minutes, and
deliberately the *same volume* — 15 coverage points against the baseline's 14
and 16. Writing a lighter issue would have moved two variables and measured
neither. ``--issue 3`` restricts the probe to the ground that issue laid down;
sampling the whole ledger would mix it with material read under the other
condition. The paper was generated before the reader saw the issue, so nothing
about it can be shaped by the reading, and it is sat cold at ~48 hours to land
inside the baseline's interval rather than beside it.

**Registered before the result, because that is the only time it is worth
writing down.** ~3/7 means the reading condition is not the story. ~6/7 means it
is, and that delivery context outranks the depth scale.

**What the rating already showed, ahead of the probe.** The reader rated issue 3
``too_advanced``, where issues 1 and 2 — same depth, same length, same subject —
were both ``just_right``. That is a result the probe cannot take away, and it
adds a third explanation to the two above: the depth was wrong all along and the
feedback loop reported the opposite. It also predicts a poor control score for a
reason that is neither attention nor volume, so the readings above now
discriminate differently: a low score indicts the depth loop rather than
exonerating attention. Recorded as **F13**.

The confound that survives: the reader knew a probe was coming, which is not how
the baseline was read. Expectancy may have landed on the rating rather than on
the retention — judging one's own grip more harshly, rather than reading more
closely. Separating those needs a fourth arm, read attentively with no test
announced, and the subscription has since dropped to depth 2, so that arm would
have to pin depth back to 3 to be comparable at all.

## Fixing the length tell — item prompt v2, 2026-08-24

v1 asked twice, in plain words, for options of similar length and hedging, and
the key still came out longest in 25 items of 32. Asking a third time was not
going to work, because the instruction was never the problem: the model writes
the true claim, then writes three lesser ones, and the true one keeps the reason
clause and the second half of the sentence. Length is a symptom of the order of
construction.

v2 changes the construction. Distractors are made by taking the keyed sentence
and changing exactly one load-bearing part — the mechanism, the ordering, the
precondition, who is responsible — leaving clause structure and level of detail
alone. A distractor derived from the true sentence inherits its shape. A hard
18-26 word band backs it up, and both are now measured on every run rather than
only under ``--calibrate``.

Ten items, same ledger points as the seed-7 paper, so the comparison is like for
like:

    key is longest        25/32 (78%)  ->   3/10 (30%)     chance 25%
    key/distractor chars  1.15 median  ->   1.03 median
    key length rank       25/2/1/4     ->   3/3/3/1        i.e. flat
    options out of band   42/128       ->   6/40
    form judge finds key  19/32 (59%)  ->   2/10 (20%)     chance 25%
    form judge: no tell   13/32 (41%)  ->   7/10 (70%)

The tell is gone by every measure that does not involve the tell detector — and
the detector still reported 10 of 10, which was the clearest evidence yet that
its rate was worthless. The screening path now uses the form judge instead, and
the old field is gone rather than deprecated: a discredited number left in the
output is a number somebody reads. Runs saved before the swap still load, and
their column is labelled as the legacy detector rather than pooled with the new
one.

First run after the swap, on a different ledger — Claude Agent SDK, depth 3,
eight items: the key is revealed in 2 of 8, which is chance, and is the longest
option in 0 of 8. The old detector would have said eight.

Two caveats that stay attached to these numbers. n=10 cannot separate 20% from
25% on its own, and it is the model-free length count that carries the result.
And "at chance" only means clean items because the same judge found a real leak
in the v1 set — on its own it is equally consistent with a judge that cannot
see. Both facts are needed; neither run means much alone.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Same reason as run_evals: progress must arrive as it happens, and everything
# printed is model-generated text against a console that may not be UTF-8.
sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")

from halflife import pricing  # noqa: E402
from halflife.config import get_settings  # noqa: E402
from halflife.db import session_scope  # noqa: E402
from halflife.generation.client import GenerationClient, GenerationError  # noqa: E402
from halflife.generation.prompts.depth_rubric import (  # noqa: E402
    DEPTH_RUBRIC,
    DEPTH_RUBRIC_VERSION,
    depth_label,
)
from halflife.models.delivery import Delivery  # noqa: E402
from halflife.models.subscription import Subscription  # noqa: E402

OUTPUT = Path(__file__).parent / "output"

# Versioned like every other prompt in the codebase. It lives here rather than
# in a prompts module because it belongs to an experiment, not to the product —
# see the note about not growing this file.
# v2 (2026-08-24): distractors are minimal edits of the keyed claim rather than
# separately written weaker claims, plus a hard 18-26 word band. v1 asked twice
# for "similar length and hedging" and measured 25/32 with the key longest.
ITEM_PROMPT_VERSION = "2"
# v2 (2026-08-24): the tell judgement moved out to FORM_SYSTEM and its own call.
BLIND_PROMPT_VERSION = "2"
FORM_PROMPT_VERSION = "1"

LETTERS = "ABCD"


# ------------------------------------------------------------------ schemas


Choice = Literal["A", "B", "C", "D"]


class Item(BaseModel):
    """Four lettered fields rather than a list of options.

    Two reasons, both learned from the API. Structured output rejects an array
    with ``minItems`` above 1, so a four-element list cannot be constrained in
    the schema at all — it would arrive with three options or six and be caught,
    if at all, downstream. And a letter is a far steadier answer key than a
    0-based index: off-by-one on ``correct`` silently inverts the result of the
    whole experiment, and nothing about the output would look wrong.
    """

    subject: str = Field(
        description="The subject this probes, as a short topic phrase suitable for a "
        "subscription — e.g. 'RFC destination trust in cross-system calls'. Not a "
        "question, not a sentence."
    )
    stem: str = Field(description="The question. One or two sentences.")
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct: Choice = Field(description="The letter of the correct option.")
    rationale: str = Field(
        description="One or two sentences: why the correct option is correct and what "
        "the most tempting wrong option gets wrong."
    )

    @property
    def options(self) -> list[str]:
        return [self.option_a, self.option_b, self.option_c, self.option_d]


class Attempt(BaseModel):
    choice: Choice
    basis: Literal["knew", "eliminated", "guessed"] = Field(
        description="knew: you know this subject and recalled the answer. eliminated: you "
        "were unsure but the other options were ruled out by wording, length, implausibility "
        "or internal inconsistency. guessed: neither."
    )
    note: str = Field(description="One sentence on what decided it.")
    # This model used to carry `tell` and `tell_note` as well. Asking one call to
    # answer the item and then say whether the answer was signposted put the two
    # jobs in the wrong order: it worked out which option was true, then
    # described that option as the standout. Calibration caught it — the field
    # fired on 93% of items where a judge shown nothing but the wording found a
    # standout in 59%, and on 100% of a set that had just been fixed. The
    # judgement now belongs to FormPick, in its own call, which never answers
    # the item. Separation is the fix, so do not fold them back together.


class FormPick(BaseModel):
    stands_out: bool = Field(
        description="False if the four options are comparable in form and none is "
        "distinguishable without considering what they claim."
    )
    pick: Choice = Field(description="The option that stands out. Ignored if stands_out is false.")
    reason: str = Field(description="One sentence, about the writing only.")


# ------------------------------------------------------------------ prompts

ITEM_SYSTEM = """\
You write assessment items that detect skill decay in working professionals.

An item is a four-option multiple-choice question. It is given to someone who \
learned this subject some time ago. Its job is to come out wrong when they have \
lost the distinction it turns on, and right when they have kept it.

{rubric}

Write the item at the depth you are given. Depth sets what the reader is assumed \
to already know, not how hard the wording is. A depth 2 item may not require \
depth 4 knowledge to answer, and a depth 4 item may not be answerable from depth \
1 knowledge — if it is, it is a depth 1 item.

Rules, all of which are how items get to be worthless:

* Ask about the subject, not about any text. The reader may have learned this \
from documentation, a colleague or a production incident. Never refer to "the \
series", "the issue", "as covered", "the reading" or anything similar. If the \
question cannot be answered by someone who learned the subject elsewhere, it is \
testing recall of a source rather than knowledge of a field, and it is wrong.
* Build the options by this procedure, not by writing a good one and three \
worse ones. Write the true claim first. Then make each distractor by taking \
that sentence and changing exactly one load-bearing part of it — the mechanism, \
the ordering, the precondition, who is responsible, what is being traded off — \
leaving the clause structure, the qualifiers and the level of detail alone. A \
distractor is the same sentence with a different claim inside it.
* That is not a style preference, it is the only thing that stops the answer \
leaking. Two earlier versions of these instructions asked for options "of \
similar length and hedging". The correct option still came out longest in 25 \
items out of 32, and a judge shown nothing but the wording picked it every \
single time it thought any option stood out. A writer who knows which claim is \
true cannot stop himself giving that one the reason clause, the second half of \
the sentence and the careful qualification — and someone who knows nothing \
about the subject can see that from across the room. A distractor derived from \
the true sentence inherits its shape and cannot be picked out by shape.
* Every option must be between 18 and 26 words. Count them before you answer. \
An option outside that range is a defect regardless of how well it reads.
* Each wrong option must be wrong *in fact* — something a competent person has \
actually believed. Wrong because it is vague, self-contradictory or a caricature \
nobody holds is not a distractor; it is scenery, and it hands the answer to a \
reader who knows nothing.
* No "all of the above", "none of the above", "both A and B".
* One defensible answer. If two options are arguably right, the item is broken.
* Turn on a distinction that decays: a boundary, an ordering, a precondition, a \
failure mode, a thing that is true only under a condition. Not a name, a number, \
a default value or a piece of syntax. Those are looked up, not retained, and \
forgetting them is not decay.
"""

ITEM_USER = """\
Subject area: {topic}
Depth: {depth} — {label}

The reader has previously covered this specific ground:

  {point}

Write one item probing whether that has decayed. The item must stand on its own \
without the sentence above.

Place the correct answer at option {letter}. Set `correct` to "{letter}". This is \
assigned to you rather than chosen by you; write the true claim into that slot \
and three false ones into the others.
"""

BLIND_SYSTEM = """\
You are answering a multiple-choice question cold, as a control for item quality.

Answer it, then report honestly how you got there:

* "knew" — you know this subject and recalled the answer.
* "eliminated" — you were unsure of the subject, but the other options ruled \
themselves out through wording, length, implausibility or internal inconsistency.
* "guessed" — neither.

Do not flatter the item and do not flatter yourself. "eliminated" and "guessed" \
are the useful answers: they are how a badly built item is caught. If you \
recognised the answer only because one option was written more carefully than \
the others, that is "eliminated", not "knew".
"""

BLIND_USER = """\
{stem}

{options}
"""


FORM_SYSTEM = """\
You are copy-editing a multiple-choice question, not answering it.

Four options. Judge only how they are *written*: length, hedging, specificity, \
whether one reads like a textbook while the others read like remarks. Which one \
stands out by form?

You are not being asked which is true and the answer is not wanted. If the \
option you would pick as true is also the one that stands out, that is a fact \
about the item and it is what this is measuring — but do not reason from truth \
to form. Judge the sentences.

If no option stands out — the four are comparable in length, register and \
qualification — say so by setting `stands_out` to false. That is a real and \
common answer for a well-built item, and a forced pick when nothing stands out \
would corrupt what this measures.
"""


# ------------------------------------------------------------------ sampling


def sample_points(coverage, count: int, rng: random.Random):
    """Points spread evenly across the ledger, oldest to newest.

    Even spread rather than a uniform sample because decay is about time: a
    random draw from a 114-point ledger clusters wherever the ledger is dense,
    and the oldest points are the ones most likely to have gone. One point is
    drawn from each of ``count`` equal bands, which cannot collide: the offset
    within a band is bounded by the band's floor, and consecutive band starts
    differ by at least that.
    """
    active = [p for p in coverage if p.is_active]
    if len(active) <= count:
        return active
    band = len(active) / count
    return [
        active[min(len(active) - 1, int(i * band) + rng.randrange(max(1, int(band))))]
        for i in range(count)
    ]


def depth_of(session, point, fallback: int) -> int:
    """The depth the point was established at, not the subscription's depth now.

    These differ whenever feedback has moved the subscription, and asking a
    depth 4 question about ground covered at depth 2 tests material the reader
    was never given.
    """
    if point.delivery_id is None:
        return fallback
    delivery = session.get(Delivery, point.delivery_id)
    return delivery.depth if delivery else fallback


# ------------------------------------------------------------------ run


class Meter:
    """Counts what the run spends. Same shape as run_evals.Meter."""

    def __init__(self, client) -> None:
        self._client = client
        self.usage: dict[str, list[int]] = {}

    def generate(self, **kwargs):
        result = self._client.generate(**kwargs)
        row = self.usage.setdefault(result.model_id, [0, 0, 0])
        row[0] += 1
        row[1] += result.input_tokens or 0
        row[2] += result.output_tokens or 0
        return result

    def report(self) -> None:
        if not self.usage:
            return
        print("\nspend for this run:")
        total = 0.0
        for model, (calls, tin, tout) in sorted(self.usage.items()):
            cost = pricing.cost_usd(model, tin, tout)
            total += cost or 0.0
            price = f"  ${cost:.2f}" if cost is not None else "  (unpriced)"
            print(f"  {model}  {calls} calls  {tin:,} in  {tout:,} out{price}")
        print(f"  total ${total:.2f}")


def render_options(options: list[str]) -> str:
    return "\n".join(f"  {LETTERS[i]}. {opt}" for i, opt in enumerate(options))


def write_item(client, *, topic: str, depth: int, point: str, letter: str) -> Item:
    """Write one item with the answer key assigned rather than chosen.

    The first three items this experiment ever produced were all keyed A. Left
    to itself the model writes the true claim first and pads out three
    distractors after it, and position bias is the result. Telling it which slot
    the answer goes in is free and removes the fault entirely; asking it to
    "vary the position" could not work, because each item is a separate call
    with no sight of the others.
    """
    result = client.generate(
        system=ITEM_SYSTEM.format(rubric=DEPTH_RUBRIC),
        user=ITEM_USER.format(
            topic=topic, depth=depth, label=depth_label(depth), point=point, letter=letter
        ),
        output_model=Item,
    )
    return result.parsed


def form_pick(client, item: Item) -> FormPick:
    """Judge the wording, in a call that never answers the item.

    This is the screening path's tell detector. It replaced a field on the blind
    control, which asked one call to answer the item and then say whether the
    answer had been signposted — and which therefore reasoned from truth to
    form and flagged almost everything. Keeping the two calls apart is not
    tidiness; it is the entire reason this number can be believed.
    """
    result = client.generate(
        system=FORM_SYSTEM,
        user=BLIND_USER.format(stem=item.stem, options=render_options(item.options)),
        output_model=FormPick,
    )
    return result.parsed


def blind_attempt(client, item: Item) -> Attempt:
    """Answer the item without having seen the ledger point it came from."""
    result = client.generate(
        system=BLIND_SYSTEM,
        user=BLIND_USER.format(stem=item.stem, options=render_options(item.options)),
        output_model=Attempt,
    )
    return result.parsed


def ask(item: Item, n: int, total: int) -> str | None:
    """Put the item to the reader. Returns the chosen letter, or None to skip."""
    print(f"\n{'=' * 68}\n  Item {n} of {total}\n{'=' * 68}")
    print(f"\n{item.stem}\n")
    print(render_options(item.options))
    while True:
        raw = input("\n  answer [A-D, or s to skip, q to stop]: ").strip().lower()
        if raw in {"q", "quit"}:
            raise KeyboardInterrupt
        if raw in {"s", "skip"}:
            return None
        if len(raw) == 1 and raw.upper() in LETTERS:
            return raw.upper()
        print("  A, B, C, D, s or q.")


def suggest(item: Item, depth: int, minutes: int) -> str:
    """The subscription a failure would propose.

    ``maintaining`` rather than ``learning``, and this is the whole shape of the
    Geiger claim in one line: the reader covered this ground and lost it, which
    is decay, not a gap. Depth is the depth the material was covered at, so the
    refresher lands where the failure was rather than where the subscription
    has since drifted to.
    """
    return f"{item.subject}, {depth}, {minutes}, 3d, maintaining"


def run(sub_prefix: str, *, count: int, dry_run: bool, seed: int, reveal: bool,
        issue: int | None = None) -> int:
    settings = get_settings()
    if not settings.anthropic_api_key:
        print("This experiment uses the API path deliberately: a pinned model is what makes")
        print("item quality comparable between runs. Set ANTHROPIC_API_KEY.")
        return 2

    with session_scope() as session:
        sub = (
            session.query(Subscription)
            .filter(Subscription.id.startswith(sub_prefix))
            .one_or_none()
        )
        if sub is None:
            print(f"No subscription matching {sub_prefix!r}. Try --list.")
            return 2
        if sub.series is None or not sub.series.coverage:
            print(f"{sub.topic} has no coverage ledger yet — nothing to ask about.")
            return 2

        coverage = sub.series.coverage
        if issue is not None:
            # Restricting to one issue is what makes a controlled comparison
            # possible: hold subject, depth and length fixed, vary how the issue
            # was read, and probe only the ground that issue laid down. Sampling
            # the whole ledger would mix it with material read under other
            # conditions and measure nothing in particular.
            wanted = {
                d.id for d in sub.deliveries if d.issue_number == issue
            }
            coverage = [p for p in coverage if p.delivery_id in wanted]
            if not coverage:
                print(f"Issue {issue} has no coverage points on this series.")
                return 2
            print(f"  restricted to issue #{issue}: {len(coverage)} points")

        rng = random.Random(seed)
        chosen = sample_points(coverage, count, rng)
        # Round-robin the answer key, then shuffle, so the keys are balanced by
        # construction rather than by luck and still unguessable in order.
        keys = [LETTERS[i % 4] for i in range(len(chosen))]
        rng.shuffle(keys)
        probes = [
            {
                "point": p.point,
                "position": p.position,
                "depth": depth_of(session, p, sub.depth),
                "key": key,
            }
            for p, key in zip(chosen, keys)
        ]
        ledger_size = sum(1 for p in sub.series.coverage if p.is_active)
        topic, minutes, sub_id = sub.topic, sub.duration_minutes, sub.id

    print(f"\n{topic}")
    print(f"  {len(probes)} items sampled across {ledger_size} ledger points, "
          f"depths {min(p['depth'] for p in probes)}–{max(p['depth'] for p in probes)}, "
          f"rubric v{DEPTH_RUBRIC_VERSION}, seed {seed}\n")

    client = Meter(GenerationClient(settings))
    rows: list[dict] = []

    try:
        for n, probe in enumerate(probes, start=1):
            print(f"  writing item {n}/{len(probes)} (ledger position {probe['position']}, "
                  f"depth {probe['depth']})...")
            try:
                item = write_item(
                    client,
                    topic=topic,
                    depth=probe["depth"],
                    point=probe["point"],
                    letter=probe["key"],
                )
                control = blind_attempt(client, item)
                form = form_pick(client, item)
            except GenerationError as exc:
                print(f"    skipped — {exc}")
                continue
            rows.append(
                {
                    **probe,
                    "item": item.model_dump(),
                    "blind": control.model_dump(),
                    "blind_correct": control.choice == item.correct,
                    "form": form.model_dump(),
                    # Two distinct defects, and they are not the same fault. A
                    # standout that IS the key hands the answer over. A standout
                    # that is not the key drags the reader toward a wrong one,
                    # which is worse: it manufactures failures rather than
                    # hiding them, and a Geiger built on it would prescribe
                    # subscriptions for decay that never happened.
                    "leaks": form.stands_out and form.pick == item.correct,
                    "misleads": form.stands_out and form.pick != item.correct,
                    "keyed_as_asked": item.correct == probe["key"],
                }
            )

        if not dry_run and rows:
            print(f"\n{len(rows)} items. Answer them; nothing is scored until the end.")
            for n, row in enumerate(rows, start=1):
                item = Item.model_validate(row["item"])
                row["answer"] = ask(item, n, len(rows))
    except KeyboardInterrupt:
        print("\n  stopped.")

    report(rows, topic=topic, minutes=minutes, dry_run=dry_run, reveal=reveal)
    path = save(rows, sub_id=sub_id, topic=topic, seed=seed, minutes=minutes)
    print(f"\nwritten to {path}")
    client.report()
    return 0


# ------------------------------------------------------------------ reporting

WORD_BAND = (18, 26)


def key_longest(rows: list[dict]) -> int:
    """How many items have the correct option as the longest of the four.

    Free, deterministic, and the one number in this file that no model has a
    hand in — which is why it is printed on every run rather than only under
    --calibrate. It is also the fastest way to tell whether a change to the item
    prompt did anything: the leak was found here first, and two revisions that
    read like fixes moved it not at all.
    """
    count = 0
    for row in rows:
        item = Item.model_validate(row["item"])
        lengths = [len(o) for o in item.options]
        if LETTERS[lengths.index(max(lengths))] == item.correct:
            count += 1
    return count


def words_out_of_band(rows: list[dict]) -> int:
    low, high = WORD_BAND
    return sum(
        1
        for row in rows
        for option in Item.model_validate(row["item"]).options
        if not low <= len(option.split()) <= high
    )


def report(
    rows: list[dict], *, topic: str, minutes: int, dry_run: bool, reveal: bool = False
) -> None:
    if not rows:
        print("\nNo items were written.")
        return

    scored_any = any(r.get("answer") is not None for r in rows)
    withhold_notes = not (reveal or scored_any)

    print(f"\n{'=' * 68}\n  Item quality — two controls\n{'=' * 68}\n")
    weak = [r for r in rows if r["blind_correct"] and r["blind"]["basis"] != "knew"]
    known = [r for r in rows if r["blind_correct"] and r["blind"]["basis"] == "knew"]
    # Legacy rows recorded the judgement as blind.tell. Those runs are still
    # readable, but the number they carry is the discredited one, so it is
    # labelled rather than silently pooled with the form judge's.
    legacy = [r for r in rows if "form" not in r]
    tells = [r for r in rows if r.get("leaks") or (("form" not in r) and r["blind"].get("tell"))]
    misleads = [r for r in rows if r.get("misleads")]
    cold = sum(1 for r in rows if r["blind_correct"])
    n = len(rows)

    def line(label: str, value: str, note: str = "") -> None:
        print(f"  {label:<27} {value}{'   ' + note if note else ''}")

    line("answered cold", f"{cold}/{n}")
    line("  of which 'knew'", str(len(known)))
    line("  of which eliminated", str(len(weak)))
    line(
        "tell (legacy detector)" if legacy else "wording reveals the key",
        f"{len(tells)}/{n}",
    )
    if misleads:
        line("wording points elsewhere", f"{len(misleads)}/{n}", "(worse — see below)")
    line("key is the longest option", f"{key_longest(rows)}/{n}", "(chance 1 in 4)")
    outside = words_out_of_band(rows)
    if outside:
        low, high = WORD_BAND
        line(f"options outside {low}-{high} words", f"{outside}/{n * 4}")
    spread = "".join(sorted(r["item"]["correct"] for r in rows))
    drifted = [r for r in rows if not r["keyed_as_asked"]]
    line(
        "answer keys",
        spread or "—",
        f"({len(drifted)} ignored the assigned slot)" if drifted else "",
    )
    # The notes name the letter they are about — "B is the only option that..."
    # — so printing them before the paper is sat hands over the key. --dry-run
    # is precisely the mode you run *before* sitting it, which made this the
    # default behaviour rather than an edge case. Found the first time a paper
    # was screened and then offered to a reader: seven of ten answers were
    # already on screen. Counts and stems are safe; notes wait until scoring.
    for r in weak:
        print(f"      [{r['blind']['basis']}] {r['item']['stem'][:56]}...")
        if not withhold_notes:
            print(f"        {r['blind']['note'][:64]}")
    for r in tells + misleads:
        kind = "leak" if r in tells else "misleads"
        print(f"      [{kind}] {r['item']['stem'][:56]}...")
        if not withhold_notes:
            note = r["form"]["reason"] if "form" in r else r["blind"].get("tell_note", "")
            print(f"        {note[:64]}")
    if withhold_notes and (weak or tells or misleads):
        print("\n  (notes withheld — they name the option they are about. They are in the\n"
              "  saved JSON, and printed once the paper is scored.)")
    if weak or tells:
        print(
            "\n  Those items are defective: they can be answered without the knowledge\n"
            "  they claim to probe. A tell points AT the key, so it inflates a score —\n"
            "  a low score on them is a floor on decay rather than an artefact."
        )
    if misleads:
        print(
            f"\n  {len(misleads)} item(s) have a distractor that stands out instead of the key.\n"
            "  That is the worse fault: it drags a reader toward a wrong answer, so it\n"
            "  manufactures failures rather than hiding them. A pipeline built on these\n"
            "  would prescribe refreshers for decay that never happened."
        )
    if known:
        print(
            f"\n  {len(known)} item(s) a cold generalist knew outright. Those are fair "
            "questions\n  about the field, but they do not measure this series' decay —\n"
            "  someone who never read an issue would pass them."
        )

    scored = [r for r in rows if r.get("answer") is not None]
    if dry_run or not scored:
        print("\n  (not sat — item quality only)")
        return

    wrong = [r for r in scored if r["answer"] != r["item"]["correct"]]
    print(f"\n{'=' * 68}\n  Your score\n{'=' * 68}\n")
    print(f"  {len(scored) - len(wrong)}/{len(scored)} correct\n")
    for r in scored:
        item = r["item"]
        mark = "ok   " if r["answer"] == item["correct"] else "WRONG"
        print(f"  {mark}  d{r['depth']}  {item['stem'][:54]}...")
        if r["answer"] != item["correct"]:
            print(f"          you {r['answer']}, correct "
                  f"{item['correct']} — {item['rationale']}")

    print(f"\n{'=' * 68}\n  What HalfLife would be told to do about it\n{'=' * 68}\n")
    if not wrong:
        print("  Nothing — no failures. Which is also a result: either the material has\n"
              "  held, or the items are too easy to detect decay. The blind control above\n"
              "  is what tells those apart.")
        return
    for r in wrong:
        print(f"  {suggest(Item.model_validate(r['item']), r['depth'], minutes)}")
    print(
        f"\n  {len(wrong)} suggestion(s) from {len(scored)} items on '{topic}'.\n"
        "  The question this experiment exists to answer: would you subscribe to\n"
        "  those? A suggestion you would decline is the pipeline emitting noise,\n"
        "  and it counts against the sensor claim regardless of how good the item was."
    )


def save(rows: list[dict], *, sub_id: str, topic: str, seed: int, minutes: int,
         path: Path | None = None) -> Path:
    OUTPUT.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = path or OUTPUT / f"geiger-probe-{sub_id[:8]}-{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "subscription_id": sub_id,
                "topic": topic,
                "seed": seed,
                "duration_minutes": minutes,
                "depth_rubric_version": DEPTH_RUBRIC_VERSION,
                "item_prompt_version": ITEM_PROMPT_VERSION,
                "blind_prompt_version": BLIND_PROMPT_VERSION,
                "model_id": get_settings().model_id,
                "generated_at": stamp,
                "items": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path



def calibrate(paths: list[Path]) -> int:
    """Does the tell detector track form, or is it rationalising the answer?

    The detector flagged a tell in every item of every run, which is as
    consistent with a detector that always says yes as with uniformly leaky
    items. It cannot tell those apart on its own, because it answers the item
    first and then reports whether "the correct option" stands out — so a model
    that reasons from truth to form would produce exactly this record.

    Two controls, both against chance at 25%:

    **Length, measured not judged.** How often is the key simply the longest
    option? No model involved, nothing to rationalise, and it is the specific
    tell the item prompt was revised to forbid. If this sits at 25% the length
    complaint was wrong regardless of what any judge says.

    **A form-only judge that never sees the key.** It is asked which option
    stands out by how it is written, and may answer that none does. If its pick
    lands on the key far above chance, the leak is real and the detector was
    reporting it. If it lands at chance, the detector was describing whichever
    option it believed, and the tell count means nothing.

    The honest limit: a strong model cannot unsee which option is true, so the
    form judge is not truly blind and its agreement is an upper bound. Chance
    disagreement is therefore the informative outcome — it cannot be produced by
    the confound, while high agreement can.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        print("Needs API access. Set ANTHROPIC_API_KEY.")
        return 2

    rows: list[dict] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data["items"]:
            rows.append({**row, "source": path.name})
    if not rows:
        print("No items found in those files.")
        return 2

    print(f"\n{len(rows)} items pooled from {len(paths)} run(s)\n")

    keyed = [r for r in rows if r["item"]["correct"]]
    longest = 0
    for r in keyed:
        item = Item.model_validate(r["item"])
        lengths = {LETTERS[i]: len(o) for i, o in enumerate(item.options)}
        if max(lengths, key=lambda k: lengths[k]) == item.correct:
            longest += 1
    pct = 100 * longest / len(keyed)
    print(f"{'=' * 68}\n  Control 1 — is the key the longest option? (no model)\n{'=' * 68}\n")
    print(f"  key is longest   {longest}/{len(keyed)}  ({pct:.0f}%, chance 25%)")

    client = Meter(GenerationClient(settings))
    picks: list[dict] = []
    print(f"\n{'=' * 68}\n  Control 2 — form-only judge, never shown the key\n{'=' * 68}\n")
    try:
        for n, r in enumerate(rows, start=1):
            item = Item.model_validate(r["item"])
            print(f"  judging {n}/{len(rows)}...")
            try:
                result = client.generate(
                    system=FORM_SYSTEM,
                    user=BLIND_USER.format(
                        stem=item.stem, options=render_options(item.options)
                    ),
                    output_model=FormPick,
                )
            except GenerationError as exc:
                print(f"    skipped — {exc}")
                continue
            pick = result.parsed
            picks.append(
                {
                    "correct": item.correct,
                    "stands_out": pick.stands_out,
                    "pick": pick.pick,
                    "hit": pick.stands_out and pick.pick == item.correct,
                    "reason": pick.reason,
                    # What the run itself recorded, for comparison against this
                    # fresh judgement. Newer runs screen with the form judge, so
                    # this is a reproducibility check on the same instrument;
                    # older ones carry the discredited detector, where it is the
                    # calibration proper. The first two runs predate both.
                    "detector_said_tell": (
                        r["form"]["stands_out"] if "form" in r else r["blind"].get("tell")
                    ),
                }
            )
    except KeyboardInterrupt:
        print("\n  stopped.")

    if picks:
        flat = [p for p in picks if not p["stands_out"]]
        hits = [p for p in picks if p["hit"]]
        judged = [p for p in picks if p["detector_said_tell"] is not None]
        agreed = [p for p in judged if p["detector_said_tell"]]
        stood = [p for p in picks if p["stands_out"]]
        print(f"\n  nothing stands out   {len(flat)}/{len(picks)}"
              f"  ({100 * len(flat) / len(picks):.0f}% clean)")
        print(f"  stands out, is key   {len(hits)}/{len(picks)}"
              f"  ({100 * len(hits) / len(picks):.0f}%, chance 25%)")
        # The conditional rate is the one that answers the question. Whether an
        # item leaks and whether the leak points at the answer are different
        # facts, and pooling them understates both.
        if stood:
            print(f"  ...of those that do   {len(hits)}/{len(stood)}"
                  f"  ({100 * len(hits) / len(stood):.0f}% — when form singles one out,")
            print("                        how often is it the right one)")
        if judged:
            print(f"  detector said tell   {len(agreed)}/{len(judged)}"
                  f"  ({100 * len(agreed) / len(judged):.0f}%)")
        # Two questions share this output and must not share a verdict: "do
        # these items leak" and "does the detector work". Chance agreement means
        # the first is no — but it only means the second is no if the item set
        # is known to leak. The first version of this text asserted the second
        # unconditionally, and duly announced that the detector was noise when
        # handed a set of items that had just been fixed.
        rate = len(hits) / len(picks)
        print(f"\n{'-' * 68}")
        if rate > 0.5:
            print("  Form alone lands on the key well above chance. These items leak, and")
            print("  the leak is real rather than the detector rationalising its answer.")
            if judged and len(agreed) / len(judged) > len(stood) / len(picks) + 0.15:
                print("\n  The detector fires more often than form alone justifies, so its own")
                print("  rate overstates how many leak. Use this column, not that.")
            print("\n  Note the direction: a tell points AT the correct answer, so it can")
            print("  only inflate a score. A low score on leaky items is a floor.")
        elif rate < 0.35:
            print("  Form alone lands on the key at about chance, so nothing in the wording")
            print("  gives the answer away. Two readings, and this run cannot separate")
            print("  them on its own:")
            print("    - these items are clean, if the judge has found leaks elsewhere;")
            print("    - the judge is blind, if it has never found one.")
            print("  Compare against a pooled run over items already known to leak.")
        else:
            print("  Between chance and clear. Neither reading is supported; more items")
            print("  or a better control is needed before this decides anything.")
        if len(picks) < 20:
            print(f"\n  n={len(picks)}. Too few to separate {100 * rate:.0f}% from 25% by itself —")
            print("  read it alongside the length count above, which needs no model.")

    client.report()
    return 0


def score_saved(path: Path, answers: str) -> int:
    """Score a run that was generated earlier, from answers given as a string.

    Generating and sitting are separate acts, and forcing them into one session
    rules out the case this was written for: a reader answering somewhere the
    script's stdin does not reach. It also means a run can be generated now and
    sat cold in a week, which is a better test of decay than sitting it thirty
    seconds after the items were written.

    One letter per item, in order. ``-`` skips.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["items"]
    given = [c for c in answers.upper() if not c.isspace()]
    if len(given) != len(rows):
        print(f"{len(rows)} items but {len(given)} answers. One letter each, '-' to skip.")
        return 2
    bad = [c for c in given if c not in LETTERS and c != "-"]
    if bad:
        print(f"Not answers: {', '.join(sorted(set(bad)))}. Use A-D, or '-' to skip.")
        return 2

    for row, choice in zip(rows, given):
        row["answer"] = None if choice == "-" else choice

    report(
        rows,
        topic=data["topic"],
        minutes=data.get("duration_minutes", 5),
        dry_run=False,
    )
    save(
        rows,
        sub_id=data["subscription_id"],
        topic=data["topic"],
        seed=data["seed"],
        minutes=data.get("duration_minutes", 5),
        path=path,
    )
    print(f"\nanswers written back to {path}")
    return 0


def list_subscriptions() -> int:
    with session_scope() as session:
        subs = session.query(Subscription).all()
        if not subs:
            print("No subscriptions.")
            return 1
        print(f"\n{'id':10} {'depth':>5} {'points':>7}  topic")
        for sub in subs:
            points = len([p for p in sub.series.coverage if p.is_active]) if sub.series else 0
            print(f"{sub.id[:8]:10} {sub.depth:>5} {points:>7}  {sub.topic}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Turn coverage-ledger points into assessment items and see whether "
        "failing one names a subscription worth having.",
    )
    parser.add_argument("subscription", nargs="?", help="subscription id or unique prefix")
    parser.add_argument("--list", action="store_true", help="list subscriptions and exit")
    parser.add_argument("--items", type=int, default=10, help="how many items (default 10)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="write and screen the items without sitting the test",
    )
    parser.add_argument(
        "--seed", type=int, default=1,
        help="sampling seed — fixed so a rerun probes the same ground (default 1)",
    )
    parser.add_argument(
        "--score", metavar="FILE",
        help="score a saved run instead of generating one; needs --answers",
    )
    parser.add_argument(
        "--answers", metavar="ABCD...",
        help="one letter per item, in order, '-' to skip",
    )
    parser.add_argument(
        "--calibrate", nargs="+", metavar="FILE",
        help="pool saved runs and test whether the tell detector tracks form or is "
             "rationalising the answer",
    )
    parser.add_argument(
        "--issue", type=int, metavar="N",
        help="probe only the ground issue N laid down, for a controlled comparison "
             "between issues read under different conditions",
    )
    parser.add_argument(
        "--reveal", action="store_true",
        help="print the blind control's notes during screening — they name the correct "
             "option, so only use this on a paper nobody is going to sit",
    )
    args = parser.parse_args()

    if args.calibrate:
        return calibrate([Path(p) for p in args.calibrate])
    if args.score:
        if not args.answers:
            print("--score needs --answers, one letter per item.")
            return 2
        return score_saved(Path(args.score), args.answers)
    if args.list or not args.subscription:
        return list_subscriptions()
    return run(
        args.subscription, count=args.items, dry_run=args.dry_run, seed=args.seed,
        reveal=args.reveal, issue=args.issue,
    )


if __name__ == "__main__":
    raise SystemExit(main())
