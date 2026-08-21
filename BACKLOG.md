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
| 4 | Containerise, then Helm, k3d, EKS | Not started; gate **G2** |

## Gates

These block a step by the project's own rules. They are not ranked with the rest.

### G1 — "usable daily for a week first" (blocks step 3)

Measured 2026-08-20: issues were written and read on 3 days (16, 19, 20 August), 10 issues, all
10 read, 9 rated — 8 `just_right`, 1 `too_basic`. Three days out of five, with a three-day gap in
the middle.

The gap is the part that matters. The gate does not ask whether the tool works; it asks whether
it is opened on a day when nothing is being built for it. That question is still unanswered.

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

### D3 — two decisions the platform doc reopened

Neither is work; both are choices that change work already planned, and both are live until
somebody settles them. They are in the design doc's open items with the full argument.

- **Kubernetes or not.** The platform doc says 12-factor containers and explicitly not Kubernetes.
  Step 4 says Helm, k3d and EKS. Settling this either removes most of step 4 or keeps it.
- **Where a rubric version lives.** Rows in a database against versioned Python constants. Today a
  delivery's `depth_rubric_version` points at a commit; a database rubric points at a row, which
  is weaker unless the row is immutable. Nothing needs the change yet — the motivation is
  per-tenant domain rubrics.

### D2 — any read path over signals

No aggregate surface beyond a window count, and no per-user read path. The second one has a
standing warning attached in `CLAUDE.md`: it arrives justified by the most sympathetic case, the
data subject asking for their own data, and it is the same code as the manager's view of somebody
else. If it is ever built it needs its own decision, on the record, with an answer to that.

## Closed

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
