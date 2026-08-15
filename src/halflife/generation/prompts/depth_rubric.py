"""The depth rubric.

This is the single highest-leverage piece of text in the product. Changing it
means bumping ``DEPTH_RUBRIC_VERSION`` — every Delivery records the version it
was generated under so the eval harness can attribute quality changes.

The organising idea: depth sets *what the reader is assumed to already know*,
and therefore what may be skipped. It does not set length. Each level names its
own failure mode so the model has something concrete to check itself against;
the dominant failure in depth-parameterised generation is unconscious collapse
toward level 3 regardless of what was asked for.
"""

from __future__ import annotations

DEPTH_RUBRIC_VERSION = "1"

DEPTH_RUBRIC = """\
## Depth rubric

The depth parameter sets **what the reader is assumed to already know**, and therefore what you
are allowed to skip. It does not set length — length comes from the duration parameter. Two
pieces on the same topic at depth 2 and depth 4 should be *disjoint in content*, not one a
longer version of the other.

**Depth 1 — Orientation.** The reader has heard the term and cannot place it. Answer: what it
is, what problem it exists to solve, and where it sits relative to things they already know.
Plain language; define every term of art inline at first use. No syntax, no configuration, no
version specifics.
*Failure at this level: a glossary entry with no "so what" — correct and useless.*

**Depth 2 — Working literacy.** The reader could follow a conversation about it and recognise
when it is relevant to their work. Introduce the standard vocabulary and the main moving parts,
and — critically — how those parts relate to each other. Give one concrete canonical scenario
end to end. Still no deep configuration.
*Failure: a feature list. If the reader cannot say what talks to what, this level did not land.*

**Depth 3 — Practitioner.** The reader has done this before or is doing it now. Assume the
vocabulary; do not re-define it. Be concrete: real configuration, commands, or API shapes. Name
the decision points a practitioner actually hits, and state the default that is usually right
and why. Name the two or three things that most commonly go wrong.
*Failure: a hedged survey that never commits to a recommendation.*

**Depth 4 — Non-obvious.** The reader is competent at level 3 and wants what experience teaches.
Cover interactions between features; why it is built the way it is; second-order effects;
performance and failure characteristics under load; the cases where the obvious answer is wrong.
Assume all level-3 material and do not restate it.
*Failure: level-3 content at greater length. If a competent practitioner would say "yes, I know
that", cut it.*

**Depth 5 — Internals and edges.** The reader is at or near the limit of the published material.
Cover implementation internals and the constraints they impose; edge cases; version-specific
behaviour and known limitations or bugs; genuinely contested trade-offs where competent people
disagree; what the documentation does not say. Assume everything below.
*Failure, in two directions: asserting confident answers where the honest answer is
"undocumented" or "it depends, and here is on what" — or, having run out of genuine depth,
drifting sideways into adjacent topics. If this topic does not have enough real depth-5
material, say so plainly and go deep on the narrowest slice that does, rather than padding.*

### Calibration checks — run these before you answer

1. Name this level's assumed reader in one sentence. Would that reader learn something they did
   not already know?
2. Is there anything here that the reader one level *below* would already know? Cut it.
3. The most common failure is unconsciously regressing toward depth 3. If the requested depth is
   1, 2, 4, or 5, re-read what you have written against that level specifically.
"""


def depth_label(depth: int) -> str:
    return {
        1: "1 — Orientation",
        2: "2 — Working literacy",
        3: "3 — Practitioner",
        4: "4 — Non-obvious",
        5: "5 — Internals and edges",
    }[depth]
