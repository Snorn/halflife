"""Quality harness for the generation engine.

Two questions, both of which decide whether step 1 is worth building on:

  depth       Does the depth parameter actually change what gets written, or
              does everything collapse toward depth 3?
  continuity  Does issue 6 know what issues 1-5 established?

Both write the generated text to evals/output/ — the harness gives you numbers,
but you are the judge, and the numbers exist to tell you where to look.

    python evals/run_evals.py depth
    python evals/run_evals.py continuity

These make real API calls and cost real tokens.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# These runs take minutes per suite and print progress as they go. Without line
# buffering the output arrives in one block at the end, and a working run is
# indistinguishable from a hung one.
sys.stdout.reconfigure(line_buffering=True)

from halflife import pricing  # noqa: E402
from halflife.config import get_settings  # noqa: E402
from halflife.generation import continuity  # noqa: E402
from halflife.generation.client import GenerationClient, GenerationError  # noqa: E402
from halflife.generation.prompts import microlearning, series_plan  # noqa: E402
from halflife.generation.prompts.depth_rubric import DEPTH_RUBRIC, depth_label  # noqa: E402
from halflife.generation.schemas import GeneratedIssue, SeriesPlan  # noqa: E402
from halflife.models.base import Flavour  # noqa: E402

OUTPUT = Path(__file__).parent / "output"


# --------------------------------------------------------------------------- metering


class Meter:
    """Wraps the client and counts what a run actually spends.

    Keyed on the model named in each response rather than the configured one,
    so a server-side fallback to a different model is costed at its own rates
    instead of silently at the requested model's.
    """

    def __init__(self, client: Meter) -> None:
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
            print("\nno API calls made.")
            return

        def _calls(n: int) -> str:
            return f"{n} call" if n == 1 else f"{n} calls"

        print("\nspend for this run:")
        total_cost = 0.0
        priced = True
        for model, (calls, tokens_in, tokens_out) in sorted(self.usage.items()):
            line = f"  {model}  {_calls(calls)}  {tokens_in:,} in  {tokens_out:,} out"
            cost = pricing.cost_usd(model, tokens_in, tokens_out)
            if cost is not None:
                total_cost += cost
                line += f"  ${cost:.2f}"
            else:
                priced = False
                line += "  (unpriced model)"
            print(line)

        calls = sum(row[0] for row in self.usage.values())
        if priced:
            print(f"  total ${total_cost:.2f} over {_calls(calls)} (${total_cost / calls:.3f}/call)")
        else:
            print(f"  {_calls(calls)}; at least one model has no price on file, so no total")
        print("  excludes prompt caching, which this harness does not use.")


# --------------------------------------------------------------------------- judges


class DepthVerdict(BaseModel):
    inferred_depth: int = Field(description="Which rubric level this piece was written to, 1-5.")
    reasoning: str = Field(description="One or two sentences on what gave the level away.")


class OverlapFinding(BaseModel):
    sentence: str = Field(
        description="The full sentence from the later piece, verbatim — not a fragment."
    )
    earlier_material: str = Field(
        description="What the earlier piece established that this sentence touches."
    )
    form: str = Field(description='Either "reference" or "restatement".')
    why: str = Field(description="One sentence justifying that classification.")


class OverlapVerdict(BaseModel):
    findings: list[OverlapFinding] = Field(
        description=(
            "Every passage in the later piece touching material the earlier piece established, "
            "classified. Empty if the later piece does not touch the earlier one at all."
        )
    )


_DEPTH_JUDGE_SYSTEM = f"""\
You grade micro-learning against a depth rubric. You are given a piece of writing and must say
which level of the rubric it was written to, judging only by what it assumes the reader already
knows and what it therefore skips — not by how long or how technical it sounds.

{DEPTH_RUBRIC}
"""

_OVERLAP_JUDGE_SYSTEM = """\
You check a series of micro-learning issues for one specific fault: earlier material being
*taught again*. The series is cumulative, so a later issue invoking earlier material is normal,
expected, and correct. Report nothing else.

Classify every passage in the later piece that touches material the earlier piece established:

* **reference** — the earlier material is invoked in service of a claim the earlier piece did not
  make. It appears as a subordinate clause, an aside, or a compressed enumeration, and the
  sentence exists to say something new. Words like "still", "since", "because" often mark it.
  A reference is CORRECT. It is not a fault, and must not be reported as one.
* **restatement** — the passage exists to explain the earlier material again. A reader who had
  read the earlier issue would learn nothing from it. Typically a paragraph, a walkthrough, or a
  sequence of steps laid out as though new.

Worked examples, all taken from real output:

reference — "A connect failure is an immediate, cheap, local signal — the server is taken out of
nomination and the request goes to another candidate, safe to retry because nothing has been sent
to the client yet." Retry-safety was established earlier; here it is one clause supporting a new
contrast between crashed and sick backends.

reference — "FillObjectMetaSystemFields still resolves generateName and still assigns a UID, so
validating webhooks see a fully identified object that will never exist." "Still" refers back;
the new payload is what that costs an external inventory.

reference — "A --dry-run=server request runs the entire chain — every mutating webhook serially,
reinvocation included, every policy, every validating webhook concurrently — and returns the fully
admitted object to the client." The chain order is earlier material compressed into one aside; the
sentence exists to assert that dry-run does not skip admission.

restatement — a paragraph walking through the admission phases in order and explaining what each
one does, when the earlier issue already did exactly that.

Quote the **full sentence**, never a fragment: a fragment cannot be classified, by you or by
anyone reading your output. When genuinely torn, classify as reference — wrongly calling correct
cumulative writing a defect is the more costly error.
"""


# --------------------------------------------------------------------------- helpers


def _generate(client: Meter, *, topic: str, depth: int, minutes: int,
              issue_number: int, ledger: list[str], threads: list[str],
              plan: list[dict] | None = None, arc: str = "") -> GeneratedIssue:
    settings = get_settings()

    result = client.generate(
        system=microlearning.build_system_prompt(),
        user=microlearning.build_user_prompt(
            topic=topic,
            depth=depth,
            duration_minutes=minutes,
            word_budget=minutes * settings.words_per_minute,
            flavour=Flavour.LEARNING,
            issue_number=issue_number,
            # Default is no plan: the depth eval isolates depth and the
            # continuity eval isolates the ledger, and an arc would confound
            # both. The plan A/B is the one suite that passes a plan in.
            plan_block=continuity.render_plan_block(plan or [], arc, issue_number),
            ledger_block=continuity.render_ledger_block(ledger),
            threads_block=continuity.render_threads_block(threads),
            # No reader in an eval, so this is always the empty rendering — but
            # it has to be present, or the eval measures a prompt production
            # never sends.
            feedback_block=continuity.render_feedback_block([]),
        ),
        output_model=GeneratedIssue,
    )
    return result.parsed


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _jaccard(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9]+", a.lower()))
    tb = set(re.findall(r"[a-z0-9]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _load_cases() -> dict:
    return yaml.safe_load((Path(__file__).parent / "cases.yaml").read_text(encoding="utf-8"))


def _run_dir(kind: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return OUTPUT / f"{kind}-{stamp}"


# --------------------------------------------------------------------------- depth


def run_depth(client: Meter) -> int:
    case = _load_cases()["depth"]
    depths: list[int] = case["depths"]
    minutes: int = case["duration_minutes"]
    run = _run_dir("depth")

    # Keyed by requested depth. Aggregating across depths cancels — a rubric
    # that writes depth 2 when asked for 1 and depth 4 when asked for 5 has a
    # mean signed error near zero while discriminating at neither end.
    inferred: dict[int, list[int]] = {d: [] for d in depths}
    repeats = 0

    for topic in case["topics"]:
        print(f"\n{topic}", flush=True)
        pieces: dict[int, GeneratedIssue] = {}
        for depth in depths:
            issue = _generate(
                client, topic=topic, depth=depth, minutes=minutes,
                issue_number=1, ledger=[], threads=[],
            )
            pieces[depth] = issue
            _write(
                run / _slug(topic) / f"depth-{depth}.md",
                f"# {issue.title}\n\n_requested depth {depth} · {minutes} min_\n\n{issue.body_markdown}\n",
            )

            verdict = client.generate(
                system=_DEPTH_JUDGE_SYSTEM,
                user=f"Which rubric level was this written to?\n\n---\n{issue.body_markdown}\n---",
                output_model=DepthVerdict,
            ).parsed

            inferred[depth].append(verdict.inferred_depth)
            mark = "ok " if verdict.inferred_depth == depth else "MISS"
            print(
                f"  depth {depth} -> judged {verdict.inferred_depth}  [{mark}] {verdict.reasoning}",
                flush=True,
            )

        # The rubric's own claim: two levels apart should be disjoint, not nested.
        lo, hi = min(depths), max(depths)
        overlap = client.generate(
            system=_OVERLAP_JUDGE_SYSTEM,
            user=(
                f"Earlier piece (depth {lo}):\n---\n{pieces[lo].body_markdown}\n---\n\n"
                f"Later piece (depth {hi}):\n---\n{pieces[hi].body_markdown}\n---\n\n"
                f"Does the depth-{hi} piece re-explain material the depth-{lo} piece establishes?"
            ),
            output_model=OverlapVerdict,
        ).parsed
        repeats += min(
            1,
            _report_overlap(
                overlap, earlier=f"the depth-{lo} piece", later=f"the depth-{hi} piece"
            ),
        )

    print("\nper-depth results — read this, not the aggregate:")
    hits = total = 0
    errors: dict[int, float] = {}
    for depth in depths:
        judged = inferred[depth]
        if not judged:
            continue
        error = sum(j - depth for j in judged) / len(judged)
        errors[depth] = error
        matched = sum(1 for j in judged if j == depth)
        hits += matched
        total += len(judged)
        print(
            f"  requested {depth}: judged {judged}  "
            f"hit {matched}/{len(judged)}  signed error {error:+.2f}"
        )

    low, high = min(depths), max(depths)
    if errors.get(low, 0) > 0.25 and errors.get(high, 0) < -0.25:
        print(
            "\n  Both ends are being pulled toward the middle. The aggregate mean cancels\n"
            "  this out, which is why it is not reported: the rubric is discriminating in\n"
            "  the centre and not at the extremes."
        )

    print(f"\ndepth accuracy: {hits}/{total}   disjointness failures: {repeats}/{len(case['topics'])}")
    print(f"output: {run}")
    return 0 if hits == total and repeats == 0 else 1


# --------------------------------------------------------------------------- continuity


def _restatements(verdict: OverlapVerdict) -> list[OverlapFinding]:
    """Only re-teaching counts. References are the series working as intended."""
    return [f for f in verdict.findings if f.form.strip().lower().startswith("restate")]


def _report_overlap(verdict: OverlapVerdict, *, earlier: str, later: str, indent: str = "  ") -> int:
    restated = _restatements(verdict)
    refs = len(verdict.findings) - len(restated)
    if restated:
        print(f"{indent}[REPEATS] {later} re-explains {earlier}:")
        for finding in restated[:3]:
            print(f"{indent}    {finding.sentence.strip()[:220]}")
            print(f"{indent}      -> {finding.why.strip()}")
        return len(restated)
    print(
        f"{indent}{later} builds on {earlier} without re-teaching it "
        f"({refs} reference{'' if refs == 1 else 's'})."
    )
    return 0


def _judge_pairs(count: int) -> list[tuple[int, int]]:
    """Pairs to check, at long, medium and short range.

    Re-explanation gets likelier the further apart two issues are, but building
    on the immediately preceding issue is the legitimate case most easily
    confused with it — so check both ends and the middle.
    """
    if count < 3:
        return [(1, count)] if count > 1 else []
    candidates = {
        (1, count),                       # longest range
        (max(2, count // 3), count - 1),  # middle
        (count - 2, count),               # adjacent, late
    }
    return sorted(p for p in candidates if p[0] < p[1])


def run_continuity(client: Meter, topics: list[str] | None = None) -> int:
    case = _load_cases()["continuity"]
    count: int = case["issues"]
    depth: int = case["depth"]
    minutes: int = case["duration_minutes"]
    run = _run_dir("continuity")

    failures = 0

    for topic in topics or case["topics"]:
        print(f"\n{topic}  (depth {depth}, {count} issues)", flush=True)
        ledger: list[str] = []
        threads: list[str] = []
        bodies: list[str] = []

        for n in range(1, count + 1):
            started = time.monotonic()
            print(f"  {n}. generating...", flush=True)
            issue = _generate(
                client, topic=topic, depth=depth, minutes=minutes,
                issue_number=n, ledger=ledger, threads=threads,
            )
            bodies.append(issue.body_markdown)
            _write(
                run / _slug(topic) / f"issue-{n:02d}.md",
                f"# {issue.title}\n\n{issue.body_markdown}\n\n---\n"
                + "\n".join(f"- {p}" for p in issue.covered_points_added),
            )
            print(f"  {n}. {issue.title}  [{time.monotonic() - started:.0f}s]", flush=True)

            # Deterministic signal: did this issue's new points restate old ones?
            for new in issue.covered_points_added:
                for old in ledger:
                    score = _jaccard(new, old)
                    if score > 0.6:
                        failures += 1
                        print(f"     [near-duplicate {score:.2f}] {new!r} ~ {old!r}")

            ledger.extend(issue.covered_points_added)
            threads = issue.open_threads

        # Judge signal at three ranges. Judging only 1-vs-N samples one pair in
        # fifteen for a six-issue series, and the two observed failures both
        # happened to be that pair — which is luck, not coverage.
        for earlier, later in _judge_pairs(count):
            print(f"  judging issue {later} against issue {earlier}...", flush=True)
            verdict = client.generate(
                system=_OVERLAP_JUDGE_SYSTEM,
                user=(
                    f"Issue {earlier}:\n---\n{bodies[earlier - 1]}\n---\n\n"
                    f"Issue {later}:\n---\n{bodies[later - 1]}\n---\n\n"
                    f"Does issue {later} re-explain anything issue {earlier} established?"
                ),
                output_model=OverlapVerdict,
            ).parsed
            failures += _report_overlap(
                verdict, earlier=f"issue {earlier}", later=f"issue {later}"
            )

        print(f"  ledger grew to {len(ledger)} points")

    print(f"\ncontinuity failures: {failures}")
    print(f"output: {run}")
    return 0 if failures == 0 else 1


# --------------------------------------------------------------------------- plan A/B


class ArcVerdict(BaseModel):
    better: str = Field(description='Which series has the better arc: "A", "B", or "tie".')
    dependency_order: str = Field(
        description="Which is better ordered so later issues can assume earlier ones, and why."
    )
    drift: str = Field(
        description="Which, if either, reads as a random walk around the topic rather than a course."
    )
    reasoning: str = Field(description="Two or three sentences.")


_ARC_JUDGE_SYSTEM = """\
You compare two micro-learning series on the same topic, written for the same reader at the same
depth. Each is presented as its ordered issue titles plus the claims each issue established.

Judge the *arc*, not the prose of any single issue:

* Dependency order — can each issue assume what earlier ones established, or does a later issue
  need something that arrives after it?
* Course versus random walk — does the sequence get somewhere, or is it a set of adjacent
  observations in arbitrary order?
* Coverage — does it reach the material that matters most for this topic at this depth, or does
  it spend its issues on a narrow corner?

One of these was written to a plan drawn up in advance; the other chose each issue from what had
already been covered. You are not told which. Do not guess — judge only what is in front of you,
and answer "tie" when they are genuinely comparable.
"""


def _run_series(
    client: Meter,
    *,
    topic: str,
    depth: int,
    minutes: int,
    count: int,
    out: Path,
    plan: list[dict] | None = None,
    arc: str = "",
) -> dict:
    ledger: list[str] = []
    threads: list[str] = []
    titles: list[str] = []
    words: list[int] = []
    per_issue: list[list[str]] = []

    for n in range(1, count + 1):
        issue = _generate(
            client, topic=topic, depth=depth, minutes=minutes,
            issue_number=n, ledger=ledger, threads=threads, plan=plan, arc=arc,
        )
        titles.append(issue.title)
        words.append(len(issue.body_markdown.split()))
        per_issue.append(list(issue.covered_points_added))
        _write(
            out / f"issue-{n:02d}.md",
            f"# {issue.title}\n\n{issue.body_markdown}\n\n---\n"
            + "\n".join(f"- {p}" for p in issue.covered_points_added),
        )
        print(f"    {n}. {issue.title}", flush=True)
        ledger.extend(issue.covered_points_added)
        threads = issue.open_threads

    near_dupes = sum(
        1
        for i, a in enumerate(ledger)
        for b in ledger[:i]
        if _jaccard(a, b) > 0.6
    )
    return {
        "titles": titles,
        "ledger": ledger,
        "per_issue": per_issue,
        "words": words,
        "near_dupes": near_dupes,
    }


def _render_arm(arm: dict) -> str:
    lines = []
    for n, (title, points) in enumerate(zip(arm["titles"], arm["per_issue"]), start=1):
        lines.append(f"{n}. {title}")
        lines.extend(f"     - {p}" for p in points)
    return "\n".join(lines)


def run_plan_ab(client: Meter) -> int:
    """Does the series plan earn the extra generation it costs at subscribe time?

    The continuity suite showed a coherent six-issue arc with no plan at all, so
    this runs both arms on the same topic and asks a blind judge which sequence
    is better ordered. The judge runs twice with the arms swapped; if it changes
    its answer, position bias is larger than the effect and the result is not
    usable.
    """
    case = _load_cases()["plan_ab"]
    topic: str = case["topic"]
    depth: int = case["depth"]
    minutes: int = case["duration_minutes"]
    count: int = case["issues"]
    run = _run_dir("plan-ab")

    print(f"\n{topic}  (depth {depth}, {count} issues per arm)", flush=True)

    print("\n  planned arm — drawing up the arc first", flush=True)
    plan_result = client.generate(
        system=series_plan.build_system_prompt(count=count),
        user=series_plan.build_user_prompt(
            topic=topic, depth=depth, duration_minutes=minutes,
            flavour=Flavour.LEARNING, count=count,
        ),
        output_model=SeriesPlan,
    ).parsed
    plan_json = continuity.plan_to_json(plan_result.issues)
    _write(
        run / "plan.md",
        f"# Plan\n\n{plan_result.arc_summary}\n\n"
        + "\n".join(f"{e['index']}. {e['title']} — {e['focus']}" for e in plan_json),
    )
    print(f"    arc: {plan_result.arc_summary}", flush=True)

    planned = _run_series(
        client, topic=topic, depth=depth, minutes=minutes, count=count,
        out=run / "planned", plan=plan_json, arc=plan_result.arc_summary,
    )

    print("\n  unplanned arm — each issue chosen from the ledger alone", flush=True)
    unplanned = _run_series(
        client, topic=topic, depth=depth, minutes=minutes, count=count,
        out=run / "unplanned",
    )

    print("\nper-arm figures:", flush=True)
    for label, arm in (("planned", planned), ("unplanned", unplanned)):
        total = len(arm["ledger"])
        print(
            f"  {label:<10} {total} coverage points "
            f"({total / count:.1f}/issue)  near-duplicates {arm['near_dupes']}  "
            f"words {min(arm['words'])}-{max(arm['words'])}"
        )

    # Blind, and run both ways round to expose position bias.
    verdicts = {}
    for orientation, (a, b) in (("planned=A", (planned, unplanned)), ("planned=B", (unplanned, planned))):
        verdict = client.generate(
            system=_ARC_JUDGE_SYSTEM,
            user=(
                f"Topic: {topic}\n\nSeries A:\n{_render_arm(a)}\n\n"
                f"Series B:\n{_render_arm(b)}\n\nWhich has the better arc?"
            ),
            output_model=ArcVerdict,
        ).parsed
        verdicts[orientation] = verdict
        winner = verdict.better.strip().upper()
        resolved = (
            "planned" if (winner == "A") == (orientation == "planned=A") and winner in {"A", "B"}
            else "unplanned" if winner in {"A", "B"}
            else "tie"
        )
        print(f"\n  [{orientation}] picks {winner} -> {resolved}")
        print(f"    order: {verdict.dependency_order}")
        print(f"    drift: {verdict.drift}")
        print(f"    {verdict.reasoning}")

    picks = []
    for orientation, verdict in verdicts.items():
        winner = verdict.better.strip().upper()
        if winner not in {"A", "B"}:
            picks.append("tie")
        else:
            picks.append("planned" if (winner == "A") == (orientation == "planned=A") else "unplanned")

    print()
    if picks[0] == picks[1]:
        print(f"consistent across both orientations: {picks[0]}")
    else:
        print(
            f"INCONSISTENT — {picks[0]} then {picks[1]}. The judge changed its answer when the\n"
            "arms were swapped, so position bias exceeds the effect. Treat this as no result."
        )
    print(f"output: {run}")
    return 0


# --------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=["depth", "continuity", "plan-ab", "all"])
    parser.add_argument(
        "--topic",
        action="append",
        help="Override the topics in cases.yaml. Repeatable. Continuity suite only.",
    )
    args = parser.parse_args()

    client = Meter(GenerationClient(get_settings()))
    try:
        if args.suite == "depth":
            return run_depth(client)
        if args.suite == "continuity":
            return run_continuity(client, args.topic)
        if args.suite == "plan-ab":
            return run_plan_ab(client)
        return run_depth(client) | run_continuity(client) | run_plan_ab(client)
    except GenerationError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 2
    finally:
        # In the finally block so an interrupted or failed run still tells you
        # what it spent before it stopped.
        client.report()


if __name__ == "__main__":
    raise SystemExit(main())
