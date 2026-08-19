# HalfLife — working constraints

Professional skill *maintenance* platform. Source of truth for product intent:
[regenerative-learning-platform-design.md](regenerative-learning-platform-design.md). This file captures the
constraints that must hold in code; read the design doc for the "why".

## Build order (deliberate — do not run ahead)

1. ✅ **Micro-learning generation engine, standalone, against SQLite.** Depth rubric + series
   continuity, driven from a CLI.
2. ✅ **MCP server + in-harness delivery** (`halflife-mcp`), targeting Claude Code and Claude Cowork.
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
    deployments where API access is not available. Extraction (step 2's other half, not yet built)
    is a local agent function using the harness model. Do not add a third path.

## The privacy boundary — non-negotiable

**The control plane never sees content, only classifications.**

- Signal body is exactly: `topics[]`, `signal_type`, `confidence`, `context_category`, `session_id`,
  `evidence`. Envelope: `schema_version`, `signal_id`, `tenant_id`, `user_id`, `timestamp`,
  `agent {harness, agent_version, extraction_prompt_version}`.
- **`evidence` is permanently `null` in v1.** The column will be nullable and nothing will write to it. It
  is there so the privacy stance is auditable, not because it is a staging area. Do not populate it, do not
  add an "opt-in" flag for it, do not add a debug mode that fills it.
- `session_id` is a **hash**. No conversation IDs, no user text, no model output, no prompt text, no
  duration or keystroke telemetry — not in the DB, not in logs, not in error payloads.
- `signal_type` is a coarse behavioural verb, never a numeric score:
  `asked_basic | asked_advanced | explained_to_ai | applied | struggled | delegated | topic_submission`.
- `confidence` is the *agent's confidence in its own classification*, not a competence score.
- **Aggregation rule:** raw signals are write-only inputs. Every human-visible surface is built from
  time-windowed aggregates. Nobody browses individual signals — including org admins. Don't build a
  signal-detail read path "for debugging".
- The extraction prompt is versioned and identical across harnesses. The topic taxonomy never ships to the
  agent — topics are free text at the edge, normalised centrally.

**Tense matters here.** None of the above is built: there is no signal table, no `evidence` column, and no
code that writes either. The schema is fixed as a specification, and that is the whole of what exists — so
this section says what must hold *when it is built*, not what holds today. Do not describe any of it in a
README, a site, or a commit message as though it were already in the schema; a claimed control nobody can
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

- Prompts live in `generation/prompts/` as versioned Python constants, never inline f-strings at the call
  site. Changing a prompt means bumping its version.
- Repositories (`repository/`) are the only place that touches the session; the CLI, and later MCP and
  FastAPI, all go through them.
- Tests that assert on model output belong in `evals/`, not `tests/`. `tests/` must be deterministic and
  offline.
