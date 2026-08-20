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

Seventh run, first against v5 (56 calls, $4.42, effort medium): 24/24, every
level 8/8, disjointness 0/8. Both open questions closed as well as this
instrument can close them.

Depth 1 swept a second consecutive time. Two clean sweeps against a 6/8 base
is about one run in a hundred by chance, which is the replication v4 was
recorded as needing. The judge's reasons keep naming the test rather than the
outcome — TLS certificate chains, which failed this level twice before v4, was
credited with "only a light scenario used to illustrate the cost rather than
teach the mechanism", which is the distinction v4 draws rather than a blanket
avoidance of scenarios.

Depth 3 on blameless incident review went 4 to 3, and the reason reads as v5's
list handed back: "artefact fields, timings, agenda minutes, verbatim
questions, thresholds for action — exactly depth 3's 'what a competent person
does' for a process topic". One cell, so the effect is single-topic, but it is
the cell the change was written for and the mechanism is visible in the
verdict.

The honest conclusion is about the instrument rather than the rubric: at 24/24
this eval has no headroom left. It cannot now detect a further improvement, and
it cannot detect a mild regression either, so running it again buys nothing
until it is made harder. Two things would make it informative again, in order
of value:

* **Measure depths 2 and 4.** Done, and unrun at the time of writing. The suite
  had only ever tested 1, 3 and 5, while every miss in seven runs was a piece
  landing in an untested neighbour — depth 1 judged 2, depth 3 judged 4 — so
  the levels absorbing the errors were never themselves graded. A 24/24 on the
  odd levels is not a rubric known to work. The full set is now 108 calls,
  around $8.70. Read the next run for depths 2 and 4 alone: the odd levels have
  passed twice and will mostly restate what is already known.
* **Harder topics.** Seven of the eight were technical, and the one practice
  topic produced both of the last two findings. A second one — giving feedback
  to a direct report — has since been added, and scored 5/5 with both
  disjointness pairs clean on its first run, reaching depth 5 on journal
  citations rather than source symbols. Two is still not a weighting. A set
  where the practice topics are the majority is what would say whether the
  artefact classes hold or were fitted to a single example.

Eighth run, and the first to grade all five levels (96 calls, $7.60, effort
medium):

  depth accuracy 40/40, every level 8/8, signed error 0.00 at all five
  disjointness, depth 1 vs 5:  0/8
  disjointness, depth 2 vs 4:  2/8

Depths 2 and 4 were judged correctly on all eight topics at the first attempt,
which is the better outcome than it looks: those are the levels every miss in
seven previous runs drifted into, and the concern was that they were absorbing
errors because their own descriptions were loose. They are not.

The failure is the pair. Depth 2 against depth 4 is the disjointness claim this
rubric makes in its own opening sentence, and it fails on two topics of eight
while the wide pair passes on all of them. Both failures are the same fault:

* Postgres connection pooling — the depth-4 piece re-illustrates depth 2's
  pods-times-pool-size example with fresh numbers, teaching nothing new.
* SAP Web Dispatcher — the depth-4 piece re-explains session affinity under a
  heading that restates depth 2's conclusion, adding only the cookie names, and
  then restates that conclusion again in different words.

A candidate cause, untested: depth 4 is told to "assume all level-3 material
and do not restate it", naming level 3 alone, while depth 5 is told to "assume
everything below". So depth 4 has never been told to assume depth 2, and depth
2 owns exactly the material both failures re-teach — the relationships between
the moving parts. Widening depth 4's assume-clause the way depth 5 already
words it is the obvious thing to try, and it is a hypothesis about two failures,
which is thin.

Note that this fault was invisible for seven runs. The suite compared the
widest pair, where nesting has little chance to occur, and reported 0/8 every
time. The claim the rubric actually makes was the one going unmeasured.

v6 acts on the candidate cause above: depth 4 now assumes everything below
rather than level 3 alone, worded as depth 5 already words it, and names the
two tells the judge convicted on — an example re-run with different numbers,
and a conclusion restated with one detail appended. It also says why the fault
is easy to commit, which is the pattern that worked at depth 1 in v4: re-
teaching a relationship feels like setting up the interaction you are about to
describe.

Fitted to two failures, so it is thin, and the run that checks it is
deliberately narrow — the two topics that failed, the nearest-miss control that
passed at 12 references, and the practice topic, which has produced a finding
in each of the last three runs.

Ninth run, checking v6 on four topics (48 calls, $4.03, effort medium):
20/20, and 0/4 on both disjointness pairs. Both topics that failed 2 vs 4 now
pass, and so does the nearest-miss control that passed before at 12 references.

The reference counts are the part worth reading. Postgres went from a
restatement to 10 clean references, SAP Web Dispatcher to 8, SAP HANA held at
10. Had v6 simply frightened depth 4 away from depth 2's material the counts
would have collapsed toward zero and the pieces would be thinner for it. Depth
4 still leans on depth 2 exactly as heavily; it refers instead of re-teaching,
which is what was asked for.

Weakest form of confirmation, though: the wording was fitted to those two
failures and then checked on them, n=2, one judge. The claim it supports is
"v6 did not break anything and the two known failures are gone", not that the
2-vs-4 pair is solved. The next full run is what would say that, and it should
be read for that pair before anything else.

Tenth run, nine topics, and the first test of v6 against topics it was not
fitted to (106 of 108 calls, $8.63): 44/45, and no disjointness failure in any
of the sixteen pair checks that completed.

That answers the question v6 was left with. It was written against two failures
and then checked on those same two; the 2-vs-4 pair is now clean on six further
topics it was never tuned against, including both practice topics, where depth
2's account of the relationships is the only thing depth 4 has to lean on.
Depth 3 on giving feedback also passed on its first outing in the standing set,
which is v5's practice artefact class holding on a topic it was not written
against — it had rested on blameless incident review alone until now.

The single miss is TLS certificate chains at depth 4, judged 5, on named
OpenSSL flags, an RFC section and a dated CA expiry. Depth 4 held on the other
eight, so the likeliest reading is that TLS has the richest artefact supply in
the set and a depth-4 piece there reaches for citations whatever the rubric
says. It is still the level v6 rewrote, and the first depth-4 miss ever
recorded, so it wants a second run before it is dismissed as topic noise.

Two caveats on the run itself. A judge call overran its token ceiling on the
last topic, so its two pair checks never ran and the numbers above were
reconstructed from the log rather than reported by the harness; the suite no
longer discards a run over one failed call. That topic was re-run alone
afterwards and scored 5/5 with both pairs clean, on freshly generated pieces —
which is a separate sample, not the missing cells filled in.

Eleventh run, nine topics, all 108 calls completed ($8.64): 44/45, and 0/9 on
both disjointness pairs — the first run in which every pair check ran and every
one passed.

  requested 1: 8/9   requested 2: 9/9   requested 3: 9/9
  requested 4: 9/9   requested 5: 9/9

The depth-4 miss did not reproduce. Last run TLS was judged 5 there, the only
depth-4 miss ever recorded, on a level v6 had just rewritten; this run depth 4
is 9/9. So v6 did not trade the 2-vs-4 boundary for a 4-vs-5 one, which was the
open worry, and that reading — TLS has the richest artefact supply in the set,
so a depth-4 piece there sometimes reaches for citations — now has a second run
behind it.

TLS missed at depth 1 instead, convicted in almost the words v4 was written in:
vocabulary correctly withheld, then the mechanism taught and a failure walked
end to end. It had passed that level twice since v4. Across five runs TLS has
now missed depth 1 three times and depth 4 once, with the miss moving between
levels, which is the same stable-rate/unstable-membership pattern recorded for
depth 1 above rather than a rubric hole. If anything here deserves attention it
is that one topic supplies most of the misses in the set.

Depth 3 on giving feedback passed a second time, on a "named four-field
artefact, thresholds, exact wording to use". Two runs is not proof, but v5's
practice artefact class no longer rests on the single topic it was written
against.

On reader ratings, which are the other thing that looks like evidence: six
deliveries have been rated by the one person reading them, all "just right".
That is not weak evidence, it is **non-independent** evidence — the rater is
the person who curated the rubric through six versions, and someone who has
spent a day tuning a scale will read output as landing on it. Do not treat a
run of "just right" as validation, and do not read this as the reader being
generous either; the ratings and the rubric simply do not have separate
sources.

Two things would be independent, and neither exists yet. **Ambient signals**,
because extraction classifies what a person actually did rather than what they
say about a piece of writing — a `struggled` on a subject they have been
reading about at depth 4 is a contradiction the reader cannot produce by being
agreeable. And **other readers**, who did not build the thing and have no stake
in it working.

Until one of those arrives, the depth rubric has exactly one instrument — a
judge model, run against topics chosen by the same person who wrote the rubric
it grades.

**First cross-harness datum, and it is not good.** Everything above was
measured on output written by one harness. Claude Cowork wrote issue 4 of a
depth-1 series through the same MCP tools, the same rubric and the same brief,
and the judge scored it **depth 4 against a requested depth 1** — a three-level
miss, where every depth-1 miss in eleven runs had been judged 2. The reasoning:
it assumes the mechanism and the running example are known, and spends its words
on second-order effects and on a judgement test, which is experience-taught
material rather than orientation.

Continuity was untouched by this: the same piece scored zero restatements
against issues 1 and 2, with 8 and 7 clean references. So the ledger travelled
across harnesses and the depth rubric did not.

**That test was run, and the confound was most of it.** Three arms wrote issue 1
of a fresh depth-1 series on one topic, empty ledger, no plan — the eval's exact
conditions — and were judged blind:

  api (pinned claude-opus-5)  ->  1
  claude-code                 ->  1
  cowork                      ->  2

So Cowork missed by one level with an empty ledger and by three with a deep one.
Roughly two of those three levels were the ledger, not the harness. A depth-1
piece judged 2 is also the ordinary failure at this level — it is what every
depth-1 miss in eleven runs looked like — so one miss at n=1 is not
distinguishable from the variance already recorded here. The worst reading is
dead: the rubric is not merely a property of the harness that produced these
scores.

**What replaced it is a real finding, and the eval is structurally blind to it.**
Every issue of one depth-1 series, judged by ledger size at the moment it was
written:

  issue 1   0 points seen  ->  1
  issue 2  11 points seen  ->  1
  issue 3  21 points seen  ->  1
  issue 4  36 points seen  ->  4

Depth holds while the ledger is shallow and breaks somewhere past twenty
points. The mechanism is plausible on its face: the ledger is a page of dense
established claims, and a writer told not to re-explain any of them, on a topic
where most of the orientation ground is now taken, has nowhere to go but up. The
depth-1 instruction and the ledger instruction pull in opposite directions, and
past some ledger size the ledger wins.

This is a product defect, not a rubric one, and it is invisible to the eval by
construction: every eval piece is issue 1 of a fresh series, so the suite has
never once graded a piece written against a full ledger. Eleven runs of scores
describe the easiest case the product has.

Two candidate fixes, neither tried. Restate the depth constraint *after* the
ledger block rather than before it, so it is the last instruction rather than
the first. Or make depth-1 series cap their ledger far lower than depth-5 ones,
on the grounds that orientation genuinely runs out of ground and a ten-issue
depth-1 series may be the wrong product rather than a prompt to fix.

Note for whoever tunes this next: three rounds have now been fitted against
four topics and a single judge model. Further gains against that set are as
likely to be fitting the judge as improving the rubric — widen the topic set
before iterating again, and repeat runs before believing a two-point move.
"""

from __future__ import annotations

DEPTH_RUBRIC_VERSION = "6"

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
vocabulary; do not re-define it. Name the decision points a practitioner actually hits, state
the default that is usually right and why, and name the two or three things that most commonly
go wrong.

Be concrete, in whatever form the topic's practice takes:

* software and systems — real configuration, commands, API shapes, file paths, the values you
  would actually set;
* practice and process — the artefact produced and the fields in it, the order of the steps, who
  is in the room and for how long, the question asked in the words you would use, the threshold
  at which you act rather than wait.

Concreteness at this level is what a competent person **does**. What experience teaches them to
weigh — second-order effects, the cases where the obvious move is wrong, where competent people
disagree — is depth 4. A topic with nothing to configure is not licence to reach for that
material: it has its own concrete practice, and that is what this level owes.
*Failure: a hedged survey that never commits to a recommendation. On topics with nothing to
configure the failure inverts, and is the more likely one: experience-taught judgement standing
in for the concrete practice, which is depth 4 arriving a level early.*

**Depth 4 — Non-obvious.** The reader is competent at level 3 and wants what experience teaches.
Cover interactions between features; why it is built the way it is; second-order effects;
performance and failure characteristics under load; the cases where the obvious answer is wrong.

**Assume everything below and restate none of it.** Not level 3's configuration, and not depth
2's account of how the parts relate — that second one is what actually gets re-taught here, and
it is easy to miss, because re-teaching a relationship feels like setting up the interaction you
are about to describe. Two tells, both from real depth-4 drafts convicted of re-explaining
depth 2:

* **A re-illustrated example.** Running depth 2's example again with different numbers teaches
  nothing. If the numbers are the only thing that changed, cut it.
* **A restated conclusion.** A heading or a sentence that says what depth 2 already concluded,
  with one further detail appended, is a restatement with decoration. Put the conclusion in a
  clause and spend the sentence on what follows from it.

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
