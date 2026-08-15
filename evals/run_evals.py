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

from halflife.config import get_settings  # noqa: E402
from halflife.generation import continuity  # noqa: E402
from halflife.generation.client import GenerationClient, GenerationError  # noqa: E402
from halflife.generation.prompts import microlearning, series_plan  # noqa: E402
from halflife.generation.prompts.depth_rubric import DEPTH_RUBRIC, depth_label  # noqa: E402
from halflife.generation.schemas import GeneratedIssue, SeriesPlan  # noqa: E402
from halflife.models.base import Flavour  # noqa: E402

OUTPUT = Path(__file__).parent / "output"


# --------------------------------------------------------------------------- judges


class DepthVerdict(BaseModel):
    inferred_depth: int = Field(description="Which rubric level this piece was written to, 1-5.")
    reasoning: str = Field(description="One or two sentences on what gave the level away.")


class OverlapVerdict(BaseModel):
    restates_earlier_material: bool = Field(
        description="True if the later piece re-explains something the earlier piece established."
    )
    examples: list[str] = Field(description="Quoted phrases that are re-explained. Empty if none.")


_DEPTH_JUDGE_SYSTEM = f"""\
You grade micro-learning against a depth rubric. You are given a piece of writing and must say
which level of the rubric it was written to, judging only by what it assumes the reader already
knows and what it therefore skips — not by how long or how technical it sounds.

{DEPTH_RUBRIC}
"""

_OVERLAP_JUDGE_SYSTEM = """\
You check a series of micro-learning issues for redundancy. The series is cumulative: a later
issue may refer to earlier material in passing to build on it, but it must not teach it again.

Referring in a clause ("since the dispatcher terminates TLS itself, ...") is correct and is NOT
redundancy. Explaining the same thing a second time is redundancy, even if the wording differs.
"""


# --------------------------------------------------------------------------- helpers


def _generate(client: GenerationClient, *, topic: str, depth: int, minutes: int,
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


def run_depth(client: GenerationClient) -> int:
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
        status = "REPEATS" if overlap.restates_earlier_material else "disjoint"
        if overlap.restates_earlier_material:
            repeats += 1
        print(f"  depth {lo} vs {hi}: {status}")
        for example in overlap.examples[:3]:
            print(f"      - {example}")

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


def run_continuity(client: GenerationClient) -> int:
    case = _load_cases()["continuity"]
    count: int = case["issues"]
    depth: int = case["depth"]
    minutes: int = case["duration_minutes"]
    run = _run_dir("continuity")

    failures = 0

    for topic in case["topics"]:
        print(f"\n{topic}  (depth {depth}, {count} issues)", flush=True)
        ledger: list[str] = []
        threads: list[str] = []
        bodies: list[str] = []

        for n in range(1, count + 1):
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
            print(f"  {n}. {issue.title}", flush=True)

            # Deterministic signal: did this issue's new points restate old ones?
            for new in issue.covered_points_added:
                for old in ledger:
                    score = _jaccard(new, old)
                    if score > 0.6:
                        failures += 1
                        print(f"     [near-duplicate {score:.2f}] {new!r} ~ {old!r}")

            ledger.extend(issue.covered_points_added)
            threads = issue.open_threads

        # Judge signal: does the last issue re-teach the first?
        verdict = client.generate(
            system=_OVERLAP_JUDGE_SYSTEM,
            user=(
                f"Issue 1:\n---\n{bodies[0]}\n---\n\n"
                f"Issue {count}:\n---\n{bodies[-1]}\n---\n\n"
                f"Does issue {count} re-explain anything issue 1 established?"
            ),
            output_model=OverlapVerdict,
        ).parsed
        if verdict.restates_earlier_material:
            failures += 1
            print(f"  [REPEATS] issue {count} re-explains issue 1:")
            for example in verdict.examples[:3]:
                print(f"      - {example}")
        else:
            print(f"  issue {count} does not re-explain issue 1.")

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
    client: GenerationClient,
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


def run_plan_ab(client: GenerationClient) -> int:
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
    args = parser.parse_args()

    client = GenerationClient(get_settings())
    try:
        if args.suite == "depth":
            return run_depth(client)
        if args.suite == "continuity":
            return run_continuity(client)
        if args.suite == "plan-ab":
            return run_plan_ab(client)
        return run_depth(client) | run_continuity(client) | run_plan_ab(client)
    except GenerationError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
