# HalfLife — working constraints

Professional skill *maintenance* platform. Source of truth for product intent:
[regenerative-learning-platform-design.md](regenerative-learning-platform-design.md). This file captures the
constraints that must hold in code; read the design doc for the "why".

## Build order (deliberate — do not run ahead)

1. ✅ **Micro-learning generation engine, standalone, against SQLite.** Depth rubric + series
   continuity, driven from a CLI.
2. ✅ **MCP server + in-harness delivery and extraction** (`halflife-mcp`), targeting Claude Code
   and Claude Cowork. Extraction runs only when the user asks for it — there is no ambient capture.
   Both harnesses verified end to end: attach, guide, subscriptions, brief, record, read. Cowork
   shares the same SQLite file rather than being sandboxed from it. What differed was quality, not
   plumbing — its issue was judged three levels off the requested depth while its continuity was
   clean, which `depth_rubric.py` records in full. Plumbing being harness-agnostic does not make
   output harness-agnostic, and nothing here should be written as though it does.
3. Wrap in FastAPI; move to Postgres; add tenancy enforcement.
4. Containerise → Helm → k3d → EKS.

Step 2 was brought forward, ahead of the "usable daily for a week first" gate, because the
deployment environment turned out to forbid API spend without procurement. In-harness generation
is not a workaround for that: it removes the carve-out below by which generation used the API
while extraction used the harness's model, so the "thick agent uses the harness's own model" rule
now holds for both. The cost is real and is recorded in the README — no unattended delivery, and
no pinned model, therefore no comparable quality measurement on the harness path.

**Two generation backends, one set of prompts.** `engine.build_brief` / `engine.record_issue` are
the seam. The API path (`generate_next`) stays for evals and prompt tuning, where a pinned model
is the whole point; the harness path serves anyone without API access. Every `Delivery` records
`source` (`api` | `harness`), and `model_id` / `effort` are nullable rather than guessed.

**Gate on step 4 — dependencies must be locked before anything is deployed.** `pyproject.toml`
declares floor pins (`anthropic>=0.69`, `mcp>=2.0`, and six others) and there is no lockfile, so
two installs a week apart resolve to different code. That is fine for a single machine where the
person running it is the person who broke it, and it is how a supply-chain compromise reaches a
server: a transitive release lands between builds and nothing records what was there before. Add
a lockfile and pin the image build to it as part of containerisation, not after. Raised by static
review 2026-08-19; nothing else from that pass is outstanding.

**Do NOT scaffold, stub, or add config for:** Kubernetes, Helm, Dockerfiles, SSO/OIDC/Keycloak, multi-tenant
auth, dashboards, the skill graph, or connectors. Not "just a placeholder", not "while we're here". If a
step-1 change seems to need one of these, say so and stop rather than adding it.

## Stack

- Python + FastAPI (FastAPI not until step 3), SQLAlchemy 2.0 + Alembic.
- SQLite for local dev (step 1). Postgres from step 3. Write SQLAlchemy that runs on both — no SQLite-only
  types, no Postgres-only types until step 3.
- Generation calls the Anthropic API directly with the `anthropic` Python SDK, model `claude-opus-5`.
  Thinking is on by default on that model; control depth with `output_config={"effort": ...}`, not
  `budget_tokens` (removed — 400s). No `temperature`/`top_p`/`top_k` (removed — 400s). Stream anything with
  large `max_tokens`.
  - As of step 2 there are two backends. **API generation** is the control-plane path, used for
    evals and prompt tuning, and is the only one whose output is comparable across deliveries.
    **Harness generation** runs the same prompts through the user's own tool via MCP, for
    deployments where API access is not available. **Extraction** is step 2's other half and is
    now built: a local agent function using the harness model, on the same brief/record seam, so
    conversation text is never an argument to anything in this codebase. Do not add a third path.

## The privacy boundary — non-negotiable

**The control plane never sees content, only classifications.**

- Signal body is exactly: `topics[]`, `signal_type`, `confidence`, `context_category`, `session_id`,
  `evidence`. Envelope: `schema_version`, `signal_id`, `tenant_id`, `user_id`, `timestamp`,
  `agent {harness, agent_version, extraction_prompt_version}`.
- **`evidence` is permanently `null` in v1.** The column exists, is nullable, and nothing writes it —
  `repository.signals.assert_no_content` refuses any row that carries one, so this is enforced rather than
  intended. It is there so the privacy stance is auditable, not because it is a staging area. Do not
  populate it, do not add an "opt-in" flag for it, do not add a debug mode that fills it.
- `session_id` is a **hash**. No conversation IDs, no user text, no model output, no prompt text, no
  duration or keystroke telemetry — not in the DB, not in logs, not in error payloads.
- `signal_type` is a coarse behavioural verb, never a numeric score:
  `asked_basic | asked_advanced | explained_to_ai | applied | struggled | delegated | topic_submission`.
- `confidence` is the *agent's confidence in its own classification*, not a competence score.
- **Aggregation rule:** raw signals are write-only inputs. Every human-visible surface is built from
  time-windowed aggregates. Nobody browses individual signals — including org admins. Don't build a
  signal-detail read path "for debugging".
- **The exception is the person the signals are about.** They may read their own, and today that needs
  no feature: the rows are in their own SQLite file and `sqlite3` reads them. Owning your own data is
  not the same as the product offering a way to browse it, and this note exists to keep the two apart
  rather than to license the second.

  It is specifically **not** a warrant for a per-user signal endpoint when there is a server. Serving a
  user their own rows means building exactly the read path this rule forbids, and every such path
  arrives justified by the most sympathetic case — the data subject asking for their own data. If it is
  ever built it needs its own decision, taken on the record, with an answer to how it is kept from
  becoming the manager's view of somebody else.
- The extraction prompt is versioned and identical across harnesses. The topic taxonomy never ships to the
  agent — topics are free text at the edge, normalised centrally.

**What is built, precisely.** The signal table exists and extraction writes to it, on request only. The
`evidence` column exists and is refused a value. There is no read path for individual signals and no
aggregate surface beyond a window count — nothing consumes signals yet, and the control plane that would
does not exist.

The tense of this section still matters. Everything above about aggregation, org admins and the control
plane describes what must hold *when there is one*, not what holds today. Do not describe any unbuilt part
in a README, a site or a commit message as though it were already there; a claimed control nobody can
inspect is worse than an admitted gap. That mistake has been made once already, from this very wording.

## Data model rules

- `tenant_id` is first-class on **every** table from day one, including in step 1 where it is a constant
  local value. Single-tenant deployment must be a deployment change later, not code surgery.
- Every generated micro-learning records the prompt versions that produced it (`depth_rubric_version`,
  `generation_prompt_version`, `model_id`, `effort`). Without this the eval harness can't attribute quality
  changes.
- Team-visible surfaces are aggregate-only, enforced at the API layer (step 3). Per-user profiles are
  visible only to the user themselves.

## Generation engine invariants (step 1)

- **Depth is anchored by an explicit rubric in the prompt**, versioned as a constant. Depth 1–5.
  Raising depth changes *what the reader is assumed to already know*, not the word count.
- **Continuity is structured, not a prose blob:** a series plan (advisory arc), an append-only coverage
  ledger, and open threads. Each generation is told what has been covered and must not re-explain it.
- Frequency default caps at daily; hourly exists for cramming.
- Two subscription flavours, labelled distinctly in the data and the prompt: **learning** (new topics) and
  **maintaining** (refreshers on strong skills; gentler frequency, depth matched to claimed strength).
- Reader feedback is `too_basic | just_right | too_advanced` and auto-adjusts the subscription's depth.

## Conventions

- Prompts live in a `prompts` module as versioned Python constants, never inline f-strings at the call
  site — `generation/prompts/` for the writing prompts, `extraction/prompts.py` for the signal one.
  Changing a prompt means bumping its version, and every row it produced records that version.
- Repositories (`repository/`) are the only place that touches the session; the CLI, and later MCP and
  FastAPI, all go through them.
- Tests that assert on model output belong in `evals/`, not `tests/`. `tests/` must be deterministic and
  offline.
- **The product name is `HalfLife` in prose, everywhere.** Two spellings are not the name and must not be
  "corrected": code identifiers (the `halflife` command, `halflife-mcp`, the `halflife_*` MCP tools,
  `HALFLIFE_*` variables, import paths, the repository URL) are API surface, and the physics term in
  "every skill has a half-life" is a different word. `tests/test_naming.py` enforces this across the
  README, this file, the microsite, `NOTICE`, the evals README and the design doc.
