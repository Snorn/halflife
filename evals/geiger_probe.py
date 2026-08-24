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

**The blind control.** Every item is then attempted by a second call that has
never seen the ledger point, and which reports whether it *knew* the answer,
*eliminated* its way there, or *guessed*. Two different faults show up here.
An item eliminated or guessed correctly has bad distractors and measures
test-craft. An item genuinely known cold is a fair question about the field,
but it is not measuring the decay of this series — a well-read generalist
would pass it without ever having read an issue. Both are reported; only the
first is a defect.

That control is not enough on its own, which the first run showed within two
items: both were answered "knew", and one of them had the correct option as the
longest and most hedged of the four — the oldest tell in multiple choice, and
the one the item prompt explicitly forbids. A solver that knows the subject
reports "knew" honestly and never has to notice the tell. So the tell is asked
about separately, and judged for a reader who does *not* know the subject,
because that reader is the only one an item detecting decay is built for.

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

**Do not trust the tell detector further than this.** It is the same model, and
a detector asked whether a tell exists has every reason to find one; nine for
nine is as consistent with an over-firing detector as with uniformly defective
items. The notes it gives are specific and check out on inspection, which is
why the finding is stated at all. Calibrating it properly means running it over
items from a real certification exam, which are known-good, and seeing what it
flags there. Until that is done, the tell count is evidence and not a
measurement, and the difference should not be quietly dropped.
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
ITEM_PROMPT_VERSION = "1"
BLIND_PROMPT_VERSION = "1"

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
    # Asked separately from basis, because the two come apart and the first run
    # showed it inside two items: a solver that knows the subject answers "knew"
    # and never notices that the correct option was also the longest and most
    # qualified. The tell is still there for a reader who has lost the subject,
    # and that reader is the only one the item exists for.
    tell: bool = Field(
        description="True if the correct option is identifiable from surface form alone: "
        "longest, most hedged, most specific, or the only one written in the register of a "
        "textbook answer. Judge this independently of whether you knew the subject — answer "
        "True if someone with no knowledge of the field could pick it out."
    )
    tell_note: str = Field(description="If tell is true, what gives it away. Otherwise empty.")


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
* Write the four options as four competing claims before deciding which is \
true. Every wrong option must be wrong *in fact* — something a competent person \
has actually believed, stated with the same confidence as the true one. A \
distractor that is vague, self-contradictory, an obvious strawman, or a \
caricature nobody holds is not a distractor; it is scenery, and it hands the \
answer to a reader who knows nothing.
* All four options must be within a few words of the same length and carry the \
same amount of hedging. If the true option is the balanced, careful, qualified \
one and the other three are blunt, the item is answerable on register alone by \
someone who has never heard of the subject. This is the single most common way \
these items fail, and length is the tell that gives it away.
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

Then, separately and regardless of how you answered, judge whether the correct
option is identifiable from its surface form: the longest, the most hedged, the
most specific, the only one that reads like a textbook. Knowing the subject does
not excuse the item. Report the tell even when you answered from knowledge — the
reader this item is built for is the one who has lost the knowledge, and a tell
hands them the answer.
"""

BLIND_USER = """\
{stem}

{options}
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


def run(sub_prefix: str, *, count: int, dry_run: bool, seed: int) -> int:
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

        rng = random.Random(seed)
        chosen = sample_points(sub.series.coverage, count, rng)
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
            except GenerationError as exc:
                print(f"    skipped — {exc}")
                continue
            rows.append(
                {
                    **probe,
                    "item": item.model_dump(),
                    "blind": control.model_dump(),
                    "blind_correct": control.choice == item.correct,
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

    report(rows, topic=topic, minutes=minutes, dry_run=dry_run)
    path = save(rows, sub_id=sub_id, topic=topic, seed=seed)
    print(f"\nwritten to {path}")
    client.report()
    return 0


# ------------------------------------------------------------------ reporting


def report(rows: list[dict], *, topic: str, minutes: int, dry_run: bool) -> None:
    if not rows:
        print("\nNo items were written.")
        return

    print(f"\n{'=' * 68}\n  Item quality — the blind control\n{'=' * 68}\n")
    weak = [r for r in rows if r["blind_correct"] and r["blind"]["basis"] != "knew"]
    known = [r for r in rows if r["blind_correct"] and r["blind"]["basis"] == "knew"]
    tells = [r for r in rows if r["blind"]["tell"]]
    cold = sum(1 for r in rows if r["blind_correct"])
    print(f"  answered cold             {cold}/{len(rows)}")
    print(f"    of which 'knew'         {len(known)}")
    print(f"    of which eliminated     {len(weak)}")
    print(f"  correct option has a tell {len(tells)}/{len(rows)}")
    spread = "".join(sorted(r["item"]["correct"] for r in rows))
    drifted = [r for r in rows if not r["keyed_as_asked"]]
    print(f"  answer keys               {spread or '—'}"
          + (f"   ({len(drifted)} ignored the assigned slot)" if drifted else ""))
    for r in weak:
        print(f"      [{r['blind']['basis']}] {r['item']['stem'][:56]}...")
        print(f"        {r['blind']['note'][:64]}")
    for r in tells:
        print(f"      [tell] {r['item']['stem'][:56]}...")
        print(f"        {r['blind']['tell_note'][:64]}")
    if weak or tells:
        print(
            "\n  Those items are defective: they can be answered without the knowledge\n"
            "  they claim to probe, so a failure rate measured on them means nothing."
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


def save(rows: list[dict], *, sub_id: str, topic: str, seed: int) -> Path:
    OUTPUT.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = OUTPUT / f"geiger-probe-{sub_id[:8]}-{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "subscription_id": sub_id,
                "topic": topic,
                "seed": seed,
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
    args = parser.parse_args()

    if args.list or not args.subscription:
        return list_subscriptions()
    return run(
        args.subscription, count=args.items, dry_run=args.dry_run, seed=args.seed
    )


if __name__ == "__main__":
    raise SystemExit(main())
