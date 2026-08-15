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

from halflife.config import get_settings  # noqa: E402
from halflife.generation import continuity  # noqa: E402
from halflife.generation.client import GenerationClient, GenerationError  # noqa: E402
from halflife.generation.prompts import microlearning  # noqa: E402
from halflife.generation.prompts.depth_rubric import DEPTH_RUBRIC, depth_label  # noqa: E402
from halflife.generation.schemas import GeneratedIssue  # noqa: E402
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
              issue_number: int, ledger: list[str], threads: list[str]) -> GeneratedIssue:
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
            # No plan: the depth eval isolates depth, and the continuity eval
            # isolates the ledger. Both would be confounded by an arc.
            plan_block=continuity.render_plan_block([], "", issue_number),
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

    hits = 0
    total = 0
    off_by = []

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

            total += 1
            delta = verdict.inferred_depth - depth
            off_by.append(delta)
            mark = "ok " if delta == 0 else "MISS"
            if delta == 0:
                hits += 1
            print(f"  depth {depth} -> judged {verdict.inferred_depth}  [{mark}] {verdict.reasoning}")

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
        print(f"  depth {lo} vs {hi}: {status}")
        for example in overlap.examples[:3]:
            print(f"      - {example}")

    drift = sum(off_by) / len(off_by) if off_by else 0.0
    print(f"\ndepth accuracy: {hits}/{total}   mean signed error: {drift:+.2f}")
    if drift < -0.3:
        print("  negative drift means collapse toward the middle — the rubric is not holding.")
    print(f"output: {run}")
    return 0 if hits == total else 1


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
            print(f"  {n}. {issue.title}")

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


# --------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=["depth", "continuity", "all"])
    args = parser.parse_args()

    client = GenerationClient(get_settings())
    try:
        if args.suite == "depth":
            return run_depth(client)
        if args.suite == "continuity":
            return run_continuity(client)
        return run_depth(client) | run_continuity(client)
    except GenerationError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
