# HalfLife — backlog

Everything known to be outstanding, in one place. Until 2026-08-20 this list lived in
conversation and in the prose of `CLAUDE.md`, which meant it was rediscovered rather than
consulted.

What this file is: the open items, each with the evidence that put it there. What it is not: a
status page, a plan, or a promise. `CLAUDE.md` remains the constraints that must hold in code and
[regenerative-learning-platform-design.md](regenerative-learning-platform-design.md) remains the
product intent; where this file and either of those disagree, they win and this file is stale.

Items keep their identifier for life. Closing one moves it to the bottom with the reason, rather
than deleting it — a backlog that only ever shrinks loses the record of what was decided and why.

## Build order

| # | Step | Status |
|---|---|---|
| 1 | Generation engine, standalone, on SQLite — depth rubric + series continuity, CLI-driven | Done |
| 2 | MCP server + in-harness delivery and extraction, on Claude Code and Claude Cowork | Built; gate **G1** unmet |
| 3 | Wrap in FastAPI; move to Postgres; add tenancy enforcement | Not started |
| 4 | Containerise — 12-factor, provider-agnostic, no Kubernetes | Not started; gate **G2** |

## Gates

These block a step by the project's own rules. They are not ranked with the rest.

### G1 — "usable daily for a week first" (blocks step 3)

**Stop measuring this by hand.** `python scripts/gate.py` reports it against the live database.
Every figure quoted here before 2026-08-23 was computed ad hoc and was wrong: days were grouped
by the stored UTC date rather than the reader's local one, so at UTC+10 everything done before
10am local was filed under the previous day. The count came out short and never looked it. Fixed
in `repository.deliveries.usage_days`, with the boundary case pinned in
`tests/test_usage_days.py`.

Measured 2026-08-23: 6 days with any use (16, 19, 20, 21, 22, 23 August), longest run 5.

The run is not the number that settles this. The gate does not ask whether the tool works; it
asks whether it is opened on a day when **nothing is being built for it** — so the line to read
is `read but not built`, which stands at **1** (23 August). Every other day of use was also a day
something was generated, which is the case the gate exists to exclude.

Step 2 was already brought forward past this gate once, for a stated reason recorded in
`CLAUDE.md` — the deployment environment forbids API spend without procurement, so the harness
path could not wait. No equivalent reason applies to step 3.

Worth noting what the days of use have already produced, since it is the argument for the gate:
the compaction guard defect, the depth-1 decay finding, the stale-schema failure and the missing
reader-thread mechanism were all found by use. None were found by building.

### G2 — dependency lockfile (blocks step 4)

`pyproject.toml` declares floor pins (`anthropic>=0.69`, `mcp>=2.0`, and six others) and there is
no lockfile, so two installs a week apart resolve to different code. Tolerable on one machine
where the person running it is the person who broke it; it is also how a supply-chain compromise
reaches a server. Add the lockfile and pin the image build to it as part of containerisation, not
after. Raised by static review 2026-08-19.

## Open findings

### F1 — extraction has no eval and one real run

Six signals from one session. Classification quality is unknown.

It cannot be evaluated the way generation was. The depth eval works by having a judge read the
output, and the whole point of extraction is that the input never leaves the machine — a judge
that could score the classification would need the conversation the design exists to protect.
Whatever is built here has to measure agreement without centralising content, or measure
something else and say so.

Design-doc open item 2, "pressure-test the signal schema against a concrete scenario", is the
same gap stated from the other end and closes with this.

### F2 — the extraction trigger has a selection bias

Extraction runs only when asked, deliberately: there is no ambient capture, and that constraint
is not up for revision. The consequence is that signals arrive when the user remembers to ask,
which correlates with sessions they already believe went somewhere.

That is a bias in the one instrument meant to be free of self-report. Recorded rather than
solved, because the obvious fixes all trade against the no-ambient-capture rule, and that trade
is not worth making for an instrument nothing yet consumes.

### F3 — the coverage ledger cannot supersede a claim

The ledger is append-only. When a reader corrects something an earlier issue established, the
correction is added and the original stays. Both are then true as far as the writer of issue N+1
can tell.

Observed 2026-08-20 on the SAP Autonomous Enterprise series: a claim about inference of table
relationships was corrected by the reader, the correction went in as an open thread, and the
weaker version remained in the ledger. Harmless while a human is reading both. It stops being
harmless at compaction, which merges points without any notion of which one survives.

### F4 — depth 2 is untested at length

Only depth 1 is capped (`ISSUE_CAP_BY_DEPTH = {1: 3}` in `models/base.py`), on the measurement
that a depth-1 series was judged 1, 1, 1, then 4 as its ledger reached 36 points. A depth-4
series held at every ledger size tested, so the cause is orientation running out of ground rather
than deep ledgers pushing everything upward.

Depth 2 has not been run to that length. It may have the same finite ground, further out.

The eval cannot see this: it only ever writes issue 1 of a fresh series, which is precisely why
the depth-1 decay was found by reading rather than by testing. Any work here starts with an eval
that writes issue N of an aged series.

### F5 — the harness path has no comparable quality measurement

No pinned model, therefore no attribution. Claude Cowork produced an issue judged three levels
off the requested depth on a fresh series, with clean continuity. That single result cannot be
separated from run variance, and will not be while the model behind the harness is whatever the
user happens to have.

This is a known and accepted cost of the harness path, recorded in the README. It is here so it
is not rediscovered as a defect.

### F6 — nothing coordinates two harnesses against one database

Opened 2026-08-21 as [issues #1–#4](https://github.com/Snorn/halflife/issues), which carry the
detail. In short: `subscriptions.create` runs no dedupe query, there is no lease or conditional
write between `halflife_next_brief` and `halflife_record_issue`, no read returns anything a caller
could use to notice its picture is stale, and datetimes are stored and returned without a zone.

All four are confirmed by reading the code. The concurrency incident they were reported from did
not reproduce against the database — [#5](https://github.com/Snorn/halflife/issues/5) records what
was actually there and what is still owed. Treat the gaps as real and the report as unverified;
they are separate claims.

This is the first entry to live in the tracker rather than here. Anything with a reproduction, a
patch and a discussion belongs there; this file keeps the one-line pointer so the backlog stays
the single place to look.

### F9 — the reader-thread marker is forgeable

[Issue #8](https://github.com/Snorn/halflife/issues/8), opened 2026-08-23. `render_threads_block`
decides a thread was raised by the reader by checking whether its text starts with
`READER_THREAD_PREFIX`. Nothing verifies that on the way in, and `halflife_record_issue` replaces
`open_threads` wholesale from harness-supplied strings — so a harness can mark its own text as
reader-requested, and the next generation is told that outranks the plan.

Found by applying the trust-boundary exercise from the security series this repository generates,
to this repository. The wider result of that exercise belongs here rather than in the ticket: by
the sentence *the prompts module and the reader's typed input are trusted, everything else is
not*, most of a mature prompt is untrusted. At 96 ledger points the SAP Autonomous Enterprise
prompt is overwhelmingly harness-authored text fed back as established ground.

That is not a defect and is not separately fixable — the ledger is the product. It is recorded so
the asymmetry is on the record, and so that the thing currently protecting it is named: the
generation loop is closed, with no connectors, no file ingestion, no web fetch and no
conversation text in extraction. Every one of those absences was decided for a different reason.

### F10 — depth feedback double-counts across a backlog

[Issue #9](https://github.com/Snorn/halflife/issues/9), opened 2026-08-23.
`apply_feedback_to_depth` moves one step per rating and never reads
`Delivery.depth`, so rating several unread issues that were all written at the same depth moves
the depth once per rating. The reader answers one question and the system counts each answer as a
separate instruction.

Observed the same day: `77909d63` rated `too_advanced` took the Messages API series from depth 3
to 2, leaving `da93a46c` unread in the inbox still written at 3. Rating it honestly would reach
depth 1 on the strength of one judgement.

Unreachable under the daily cadence the product assumes — it needs a backlog, and a backlog needs
generation to have run ahead of reading. It appeared because seven issues were written in one
sitting. Anyone catching up after a week away is in the same position.

### F11 — lowering a depth collides with the ledger

Recorded 2026-08-23 as a prediction, before the outcome exists. Raising a depth is harmless: the
ledger holds less than the new level assumes. Lowering it is not symmetric, because the ledger has
already taken the ground the new level owns — the Messages API series now holds 29 points
established at depth 3, including `stop_reason` semantics, block types and statelessness, which is
depth 2's own material and is therefore marked covered and forbidden.

Issue 3 of `cf63b087` is the test. It will either go sideways, which is what the prompt tells it
to do when a level runs out of ground, or come out thin. This is the mirror of **F4**: there a
level ran out of ground by exhausting it upward, here by having it taken from below.

## Deferred by design

Not backlog in the sense of work waiting to start. Listed so that "not built" is never mistaken
for "not thought about".

### D1 — the v2 surfaces

Skill graph, dashboards, connectors, decay detection proper, auto-pause of maintenance
subscriptions on `applied` signals. `CLAUDE.md` forbids scaffolding, stubbing or adding config
for any of these, including as a placeholder.

Since 2026-08-21 the design doc also carries a platform architecture — Rutherfords, with HalfLife
and Geiger as heads on a shared rubric engine, plus an LLM gateway, Redis and async workers, and a
hosted remote MCP server. Same rule: recorded, not started. The forbidden list is not extended by
it, because everything new in it is further away than the things already on the list.

### D3 — the platform doc's two reopened decisions

Both settled on 2026-08-21 and moved to Closed. The entry stays so the identifier keeps
meaning something and so the pair stays findable together: they were the only two places where
the platform architecture and the working constraints disagreed, and knowing that the count was
two is worth as much as either answer.

### D2 — any read path over signals

No aggregate surface beyond a window count, and no per-user read path. The second one has a
standing warning attached in `CLAUDE.md`: it arrives justified by the most sympathetic case, the
data subject asking for their own data, and it is the same code as the manager's view of somebody
else. If it is ever built it needs its own decision, on the record, with an answer to that.

## Closed

- **F8 — stored text parsed as Rich console markup** — closed 2026-08-21,
  [issue #7](https://github.com/Snorn/halflife/issues/7). `_esc` wraps `rich.markup.escape` and
  every interpolation of model-written or user-typed text goes through it; 29 call sites, four of
  which the original scope missed and the tests caught. Ten tests drive each display surface
  against both a swallowed token and a crashing one.
- **F7 — `read_at` recorded neither a fetch nor a read** — closed 2026-08-21,
  [issue #6](https://github.com/Snorn/halflife/issues/6). Split into `fetched_at`, set by both
  read paths, and `read_at`, set by `set_feedback` and nowhere else. The inbox now empties on
  rating rather than on display. Migration `64cec47ead2f` re-attributed existing rows and returned
  one delivery to the inbox — the row the old column was misreporting.

- **Where a rubric version lives** — closed 2026-08-21 by scoping it. Core rubrics stay
  as versioned Python constants; per-tenant domain rubrics may be database rows if they are
  ever built. The two positions were never in conflict — one phrase was covering two kinds of
  rubric. Calibration belongs in a commit, configuration belongs in a row. A condition
  attaches to the second: append-only, version in the row's identity, or a delivery's recorded
  rubric version stops meaning anything.

- **Kubernetes or not** — closed 2026-08-21, against. Deployment is 12-factor
  containers on a provider-agnostic host, Fly or Railway first and ECS or Cloud Run later.
  Step 4 was "Containerise → Helm → k3d → EKS" and is now containerisation alone, which
  removes a local cluster, a chart to maintain and a managed control plane to pay for. The
  lockfile gate **G2** is unaffected: it was always about what goes into the image, not
  about what schedules it.

- **Ledger compaction, unrehearsed** — closed 2026-08-20. Exercised on a real series; found and
  fixed a defect where `build_compaction_brief` offered folds below the trigger threshold and
  would have re-folded its own summaries. The guard now lives in `points_to_compact`, which every
  route passes through.
- **Claude Cowork unverified** — closed 2026-08-20. Attach, guide, subscriptions, brief, record
  and read all verified against the same SQLite file. Produced the depth-decay finding. Quality
  differences remain open as **F5**.
- **Schema drift surfacing as an opaque error** — closed 2026-08-20. Reported from a second
  machine after biting twice in one session. `assert_at_head` now runs from `get_engine`, so the
  first thing that touches the database fails with the remedy rather than a stack trace.
- **Opt-in `evidence` paraphrase** — closed 2026-08-20. Listed as a v2 candidate in the design
  doc while `CLAUDE.md` forbade it by name; struck from the design doc with the reasoning
  recorded there. Two source-of-truth documents disagreeing about the same field is the condition
  under which a privacy boundary gets crossed by someone acting in good faith.
