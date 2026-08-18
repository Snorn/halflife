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

v2 moved depth 5 from 1/4 to 3/4 and disjointness failures from 2/4 to 1/4,
but depth 1 only went 0/4 to 1/4. v3 addresses the two things that run showed:

* Depth 1's misses were convicted on teaching the vocabulary and walking a
  scenario end to end — neither of which v2 forbade, and both of which are
  depth 2's deliverables. The one depth-1 success withheld the terminology
  outright. So depth 1 now avoids the standard vocabulary rather than defining
  it, and the end-to-end walk is named as depth 2's.
* Depth 5's remaining miss was SAP Web Dispatcher, judged short on "source
  symbols, notes, or version-specific bug references". v2's test named source
  code artefacts specifically, which is unreachable for proprietary software —
  a large share of what the first trial cohort will subscribe to. v3 gives
  closed-source and standards topics their own artefact classes.

Where v3 landed: depth accuracy 9/12 (v1 5/12, v2 8/12), disjointness failures
0/4 (v1 2/4, v2 1/4). Depth 3 has been 4/4 throughout. Two known ceilings, both
looking structural rather than fixable by wording:

* Depth 1 sits around 3/4. Two later runs at effort=medium showed the miss
  *moving between topics* — TLS certificate chains missed in one and scored a
  clean 1 in the next, substituting "stamp" and "working identity" for the
  standard terms. So this is a marginal call that varies run to run, not the
  per-topic structural ceiling recorded here earlier: concept topics can hit
  depth 1, they just do not do it reliably. Anything aimed at the remaining
  miss has to beat run-to-run variance, which means repeated runs rather than
  the single comparison that produced the wrong conclusion the first time.
* Depth 5 on SAP now cites SAP Notes, which it did not under v2, so the
  artefact-class change took effect; the judge still wants errata-level
  specificity the model does not appear to hold for that product.

Effort matters more than any further rubric wording. The same v3 text scores
9/12 at effort=high and 11/12 at effort=medium, reproduced across two runs, at
roughly 40% of the cost. Higher effort explores more before answering, which is
the opposite of what a tightly-constrained rubric wants. Anyone benchmarking
this rubric should state the effort level, because it moves the result by more
than two of the three revisions above did.

Fourth run at effort=medium, and the first under generation prompt v3, which
added a callback rule and a reader-feedback rule to the surrounding prompt
without touching this text: 10/12, disjointness still 0/4. Depth 3 and depth 5
were both 4/4; both misses were depth 1 judged as 2, on Kubernetes admission
controllers and TLS certificate chains.

Read that as the same 3/4-ish depth-1 ceiling rather than a regression from
11/12 — one extra miss out of twelve is inside the run-to-run variance this
docstring already records, and the topic that missed is again not stable across
runs. What is stable is the *shape* of the miss, and it has now sharpened: both
pieces withheld the standard vocabulary correctly, and were convicted on
scope — mapping relationships, contrasting alternatives, walking a scenario end
to end. v3's wording fixed the vocabulary half of that and left the scope half
implicit. If anyone takes another run at depth 1, that is the seam: constrain
what it may *do*, not only what it may *name*. Repeat runs first, per the note
below.

Fifth run, and the first against the widened eight-topic set (56 calls, $4.49,
effort medium): 22/24, disjointness 0/8. Depth 3 and depth 5 were both 8/8.
Depth 1 was 6/8, missing on Postgres connection pooling and TLS certificate
chains, both judged 2.

Three things that set was built to find out, and what it said:

* **Depth 5 does not need code to cite.** Blameless incident review — chosen
  precisely because it has no source, no RFC, no vendor notes and no version
  numbers — was judged 5 on journal volumes and page numbers, book editions and
  chapters, plus a contested trade-off. The predicted hole is not there: the
  artefact classes extend to literature, and the rubric generalises past
  configurable software.
* **The closed-source class is not carried by one topic.** SAP HANA memory
  management reached depth 5 on SAP Notes and revision caveats, as SAP Web
  Dispatcher now does. The artefact-class change in v3 holds on a second
  product rather than on the one it was written against.
* **Conceptual topics are not what breaks depth 1.** The comment in cases.yaml
  asserted that, and it was wrong even about the earlier runs. All three of the
  new conceptual topics — cgroups v2, the OAuth device flow, incident review —
  were judged 1 correctly. Both misses were configurable topics.

What depth 1 actually looks like across runs: on the original four topics it
scored 2/4 in both this run and the last, with the *identity* of the misses
swapping — Kubernetes admission controllers missed last time and was clean
here, Postgres connection pooling the reverse. Only TLS certificate chains
missed twice. So depth 1 has a stable rate and unstable membership, which is
variance, not a property of particular topics. The shape of the miss is stable
too, and is the seam recorded above: the vocabulary is correctly withheld, and
the piece then maps relationships and walks a scenario end to end anyway.

v4 changes depth 1 alone, and does not add a rule. v3 already said not to map
how the parts interconnect and not to walk a scenario end to end, and the two
misses in the wide-set run did both of those things — so the rule is not
missing, it is being ignored, which is the third time this file has recorded
that pattern. Both previous times the fix was the same: give the rule a
concrete test the writer can run against its own draft, as depth 5 got with
"name the artefact" and depth 1's vocabulary rule got with "replace the term
with an ordinary description".

So v4 names the two tells the judge actually convicted on — a sequence of
steps, and a paragraph whose subject is a part rather than the thing — and asks
for a check against each. It also says what to spend the words on instead,
because a ban with nothing behind it produces padding, and the level's stated
failure mode is thinness. And it names the quiet failure explicitly: a piece
that withholds the vocabulary correctly, exactly as asked, and then explains
the mechanism anyway.

Whether it works is unmeasured. Depth 1 has a stable rate and unstable
membership, so a single run cannot tell a real improvement from the swap that
happened between the last two runs — this needs repeated runs against the wide
set before anyone believes a number, and 6/8 is a high enough base that a real
effect is a small effect.

Sixth run, first against v4 (56 calls, $4.50, effort medium): 23/24, with
depth 1 at 8/8 — the first clean sweep of that level — depth 5 at 8/8, and
disjointness 0/8. All three topics that had ever missed depth 1 came back
clean, TLS certificate chains for the first time in three attempts, and the
judge's reasons quote v4's test back almost verbatim: "orientation plus stakes,
no parts, no walked scenario".

That is suggestive and not settled. Against the 6/8 base rate a clean sweep
comes up about one run in ten by chance, and this run carries its own warning
about variance: depth 3 fell to 7/8 on a topic whose rubric text v4 did not
touch. A level that moves without its rule changing is the reason two more runs
are needed before anyone treats 8/8 as the new rate.

The miss is worth more than the improvement, and is what v5 answers. Blameless
incident review was judged 4 at depth 3: it assumed the vocabulary correctly
and then delivered experience-taught judgement — power dynamics, timing
windows, a named disagreement between Google SRE and Allspaw — because depth
3's concreteness test asked for "real configuration, commands, or API shapes"
and a practice topic has none of those. Depth 5 had already been given artefact
classes so it could generalise past software, and it did, on literature. Depth
3 had not, so a topic with nothing to configure had nowhere to be concrete and
reached up a level for material.

v5 therefore gives depth 3 the same treatment depth 5 got in v3: name what
concreteness *is* for practice and process topics — the artefact and its
fields, the step order, who is in the room and for how long, the question in
the words you would use, the threshold at which you act — and say plainly that
having nothing to configure is not a licence to reach for judgement. Its
failure note now names the inverted failure too, since on those topics the
level fails by arriving early rather than by hedging.

Only the wide topic set could surface this. The original four are all
configurable software, so depth 3 looked like the most reliable level in the
rubric for five runs; it was untested rather than solid.

Note for whoever tunes this next: three rounds have now been fitted against
four topics and a single judge model. Further gains against that set are as
likely to be fitting the judge as improving the rubric — widen the topic set
before iterating again, and repeat runs before believing a two-point move.
"""

from __future__ import annotations

DEPTH_RUBRIC_VERSION = "4"

DEPTH_RUBRIC = """\
## Depth rubric

The depth parameter sets **what the reader is assumed to already know**, and therefore what you
are allowed to skip. It does not set length — length comes from the duration parameter. Two
pieces on the same topic at depth 2 and depth 4 should be *disjoint in content*, not one a
longer version of the other.

**Depth 1 — Orientation.** The reader has heard the term and cannot place it. Answer two things:
what it is, and what problem it exists to solve. No syntax, no configuration, no version
specifics.

Write in plain language and **avoid the standard vocabulary rather than teaching it**. Where a
term of art can be replaced by an ordinary description, replace it; where one is genuinely
unavoidable, define it in passing and move on. Handing the reader the terminology is depth 2's
deliverable, and introducing jargon in order to define it is the most common way a depth-1 piece
becomes a depth-2 piece.

Stay on the one thing. Do not map the surrounding landscape — no comparison against sibling or
adjacent components, no disambiguation from what it gets confused with, no account of how the
parts interconnect — and do not walk a scenario end to end. All of that is depth 2, and taking
it here leaves depth 2 with nothing to say.

Two tells, both taken from real depth-1 drafts that were judged depth 2. Check the draft for
each before answering:

* **A sequence.** If a passage runs *first this happens, then that, then the other*, you have
  walked a scenario. Give the outcome and cut the steps that produce it.
* **A second subject.** If a paragraph is about one of the thing's parts, or about something it
  talks to, rather than about the thing itself, it belongs to depth 2.

Spend the words on the problem instead: what goes wrong without it, who feels that, what it
costs them, and one concrete situation in which the reader would meet it. That is what keeps
orientation from thinning into a glossary entry.
*Failure at this level: a glossary entry with no "so what" — correct and useless. The other
failure is quieter and more common: a piece that withholds the vocabulary correctly, exactly as
asked, and then explains the mechanism anyway. That is depth 2 written in plain language.*

**Depth 2 — Working literacy.** The reader could follow a conversation about it and recognise
when it is relevant to their work. This level owns **the vocabulary and the relationships**: the
standard terminology, the main moving parts, how those parts relate to each other, and what it
is distinct from among the things it is commonly confused with. This is also the level that
walks one concrete canonical scenario end to end. Still no deep configuration.
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

What separates this level from depth 4 is **specificity a reader could go and check**. Depth 4 is
what experience teaches; depth 5 is what the source, the changelog, the vendor's own errata and
the bug tracker teach. Name the artefact:

* open code — the function or struct, the file, the commit or issue, the release a behaviour
  changed in;
* closed or vendor software — the vendor note or KB article number, the parameter together with
  the release its behaviour changed in, the documented default the product contradicts in
  practice;
* protocols and standards — the RFC and section, the CVE, the erratum.

Closed-source topics are not exempt from this level; they have a different artefact class, and
"there is no source to cite" is not a licence to fall back to depth 4. If you genuinely cannot
name a single checkable artefact of any kind, narrow instead.

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
