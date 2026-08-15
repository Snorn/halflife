"""The depth rubric.

This is the single highest-leverage piece of text in the product. Changing it
means bumping ``DEPTH_RUBRIC_VERSION`` — every Delivery records the version it
was generated under so the eval harness can attribute quality changes.

The organising idea: depth sets *what the reader is assumed to already know*,
and therefore what may be skipped. It does not set length. Each level names its
own failure mode so the model has something concrete to check itself against.

v2 responds to the first real eval run, which showed compression toward the
middle rather than collapse: depth 3 was judged correctly 4/4, while depth 1
was judged 2 four times out of four and depth 5 was judged 4 three times out of
four. Two causes, both defects in v1's text:

* v1's depth 1 invited "where it sits relative to things they already know",
  which is depth 2's contract. Levels 1 and 2 overlapped, so the model wrote
  the more generous one. Depth 1 now forbids landscape-mapping outright and
  depth 2 explicitly owns relationships.
* v1 described depth 5 abstractly and gave no test for it. The one topic that
  scored 5 did so on named source symbols and a commit hash, so v2 makes
  checkable specificity the explicit 4-vs-5 boundary, promotes the narrowing
  rule out of the failure note where it was being ignored, and bans the
  grounding preamble that was causing depth 5 to restate depth 1.
"""

from __future__ import annotations

DEPTH_RUBRIC_VERSION = "2"

DEPTH_RUBRIC = """\
## Depth rubric

The depth parameter sets **what the reader is assumed to already know**, and therefore what you
are allowed to skip. It does not set length — length comes from the duration parameter. Two
pieces on the same topic at depth 2 and depth 4 should be *disjoint in content*, not one a
longer version of the other.

**Depth 1 — Orientation.** The reader has heard the term and cannot place it. Answer two things:
what it is, and what problem it exists to solve. Plain language; define every term of art inline
at first use. No syntax, no configuration, no version specifics.

Stay on the one thing. Do not map the surrounding landscape — no comparison against sibling or
adjacent components, no walking through how the parts interconnect, no disambiguation from
things it gets confused with. That is depth 2's job, and reaching for it is the most common way
a depth-1 piece becomes a depth-2 piece.
*Failure at this level: a glossary entry with no "so what" — correct and useless.*

**Depth 2 — Working literacy.** The reader could follow a conversation about it and recognise
when it is relevant to their work. This level owns **relationships**: the standard vocabulary,
the main moving parts, how those parts relate to each other, and what it is distinct from among
the things it is commonly confused with. Give one concrete canonical scenario end to end. Still
no deep configuration.
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

What separates this level from depth 4 is **specificity a reader could go and check**: the name
of the function or struct, the version a behaviour changed in, the commit or issue, the default
the documentation states and the code contradicts. Depth 4 is what experience teaches; depth 5
is what the source, the changelog, and the bug tracker teach. If you cannot name a single such
artefact for this topic, you are writing depth 4 — narrow instead.

Narrowing: if the topic does not carry enough genuine depth-5 material at this length, say so in
one sentence at the top, name the slice you are going deep on, and go deep on it. This is the
expected outcome for many topics rather than an admission of failure, and it is much better than
depth-4 content under a depth-5 heading.

Open inside the problem. Do not restate premises the reader must already hold to be reading at
this level: no grounding paragraph, no recap of the mechanism, no "as you know". Your first
sentence should be one a depth-3 reader could not follow.
*Failure: asserting confident answers where the honest answer is "undocumented" or "it depends,
and here is on what" — or, having run out of genuine depth, drifting sideways into adjacent
topics instead of narrowing.*

### Calibration checks — run these before you answer

1. Name this level's assumed reader in one sentence. Would that reader learn something they did
   not already know?
2. Is there anything here that the reader one level *below* would already know? Cut it.
3. The most common failure is compression toward the middle: a depth-1 piece drifting up by
   mapping relationships, and a depth-5 piece sliding down by having nothing checkable in it.
   If the requested depth is 1 or 5, re-read against that level's extra rules specifically.
"""


def depth_label(depth: int) -> str:
    return {
        1: "1 — Orientation",
        2: "2 — Working literacy",
        3: "3 — Practitioner",
        4: "4 — Non-obvious",
        5: "5 — Internals and edges",
    }[depth]
