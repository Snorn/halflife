# HalfLife — Regenerative Learning Platform, Design Doc (v0.1)

*Ideation output, August 2026. Status: concept settled, pre-build.*

## Concept

Professional skill maintenance. Skills decay ("I was good at algebra at school; now I'd have to relearn it"). The platform assesses where people are, detects drift between what they know and what their role demands, and periodically delivers content to keep skills fresh — regenerative learning.

**Positioning:** most learning tools help you acquire something new; this one helps you *keep* what you already learned. A maintenance product, not an acquisition product — which is what makes decay, freshness and cadence the load-bearing concepts rather than courses and completion.

**Name:** **HalfLife** — the decay metaphor stated outright: every skill has one, and the product's job is to keep topping you back up before yours runs down.

## Audience

- Professional tool (career skill maintenance), not consumer.
- The design target is the forward-deployed / field engineer shape of role: constant exposure to
  unfamiliar customer stacks, high topic churn, and most of the working day spent inside an AI
  harness. Several decisions below only make sense against that user — the harness-only sensor
  surface especially.

## Architecture

- **Control plane:** cloud-native, containerised, deployable to any cloud (Helm/K8s; EKS/AKS/GKE or on-prem later). Holds API, dashboards, micro-learning scheduler/generator, skill graph store. Postgres suffices for the graph (nodes + edges tables).
- **Agent:** runs locally, **thick** — does extraction/summarisation locally using the harness's own model, ships only conclusions. Harness-agnostic via **MCP**: one MCP server, thin per-harness wrappers only where required. Targets: Copilot, Claude Cowork, Amazon Q.
- **Identity/tenancy:** SSO required (OIDC/SAML via off-the-shelf, e.g. Keycloak or Entra — no hand-rolling). Multi-tenant SaaS initially; tenant_id first-class on every table so single-tenant is a deployment change later, not code surgery.
- **Roles:** user, team lead, org admin. Team views are aggregate-only, enforced at the API layer. Per-user profiles visible only to the user themselves; manager sees team-level rollups.

## v1 scope: zero-permission

- Sensor surface is **harness conversations only** — no email, calendar, or document access. No OAuth consent screens, no security-review blockers. Connectors are deferred to a later version.
- What v1 actually delivers: (1) micro-learning subscriptions (day-one value), (2) emergent skill profile from what users ask their AI, (3) team view of aggregated topics and subscription trends. Decay detection proper arrives when connectors provide time-depth (v2).

## Micro-learning engine

User-requested subscriptions, AI-generated content:

- Parameters: **topic/domain, depth (1=basic … 5=advanced), duration (minute read), frequency (hourly/daily/weekly)**. Power-user shorthand: `sap web dispatcher, 3, 5, 1d`. Dropdowns for everyone else.
- Depth anchored by an explicit rubric in the generation prompt (1 = plain-language overview → 5 = edge cases, internals, expert nuance).
- **Continuity:** store a summary of what each series has covered; feed it into each generation so day 4 builds on days 1–3.
- Frequency default capped at daily; hourly exists for cramming scenarios.
- **Delivery: in-harness** (conversational — follow-up questions become free depth-feedback signals), with **email as the nudge**. MCP tool shape: `get_pending_microlearnings` called at session start.
- Two subscription flavours, labelled distinctly: **learning** (new topics) and **maintaining** (refreshers on strong skills — gentle default frequency, depth matched to claimed strength).

## Skill graph

- **Team-specific and emergent**, not a predefined taxonomy. Starts empty; AI-generated from ambient signals and end-user topic submissions.
- LLM pass normalises free-text topics ("k8s" → "Kubernetes"), deduplicates, proposes parent/child edges ("SAP Web Dispatcher" is-part-of "SAP Basis").
- Two tiers: shared team graph (coverage, freshness) + per-user overlays (individual strength/recency).
- Human-in-the-loop: AI proposes merges/hierarchy; users/admin confirm via a review queue. Corrections improve the normalisation prompt.
- Topics are free-text at the edge, normalised centrally — the taxonomy never ships to the agent.

## Signal schema (the privacy boundary)

Rule: **the control plane never sees content — only classifications.**

Envelope: `schema_version, signal_id, tenant_id, user_id, timestamp, agent {harness, agent_version, extraction_prompt_version}`.

Body:

```json
{
  "topics": ["SAP Web Dispatcher", "SSL termination"],
  "signal_type": "asked_basic | asked_advanced | explained_to_ai | applied | struggled | delegated | topic_submission",
  "confidence": "low | medium | high",
  "context_category": "coding | troubleshooting | research | writing | meeting-prep",
  "session_id": "hash",
  "evidence": null
}
```

Key decisions:

- Signal types are **coarse behavioural verbs, not scores** — robust to model variance across harnesses. `explained_to_ai` = strongest competence signal; `struggled` = strongest gap signal; `applied` = quiet competence.
- `confidence` = the agent's confidence in its own classification.
- `evidence` is **permanently null in v1** but present in the schema — auditable privacy stance.
- `session_id` is a hash (dedupe without content linkage). No conversation IDs, no user text, no model output, no duration/keystroke telemetry.
- Extraction prompt is versioned and identical across harnesses.
- **Aggregation rule:** raw signals are write-only inputs; every human-visible surface is built from time-windowed aggregates. Nobody browses individual signals, including org admins.
- Planned feedback loop: users can confirm/reject inferred skills; corrections are training gold.

## Dashboards

- **User:** skill profile with per-skill freshness/decay indicator (green→amber→red), active subscriptions (edit/pause), delivered-reads feed with too-basic/too-advanced feedback that auto-adjusts depth, light stats.
- **Management:** skills × team heatmap (coverage + decay risk), trending requested topics, aggregate-only.

## Onboarding flow (~10 minutes to first value)

1. **Invite** → SSO → one-screen consent showing the *actual signal schema* and the off switch. Explicit consent click, logged.
2. **Agent install** (per-harness instructions); registers via short-lived pairing code; dashboard shows "agent connected."
3. **Seed the profile** — two questions: "What are you working on right now?" (→ topics/subscriptions) and "What do you know well that others ask you about?" (→ high-confidence competence nodes). LLM proposes graph nodes; user confirms with checkboxes.
4. **First subscription** created guided; **first micro-learning generated immediately on-screen** — value in minute eight, not day two. Seeded competence topics **auto-create maintenance subscriptions**.
5. **Expectations screen:** "Profile builds itself over 2–3 weeks. Daily reads arrive in [harness], nudged by email."

In-harness first-run: one sentence ("Skill tracker active — classifications only, no content leaves. Say 'pause tracking' anytime"), then silent unless delivering or asked.

Admin flow (tenant/team/invites) stays manual/scripted for a first deployment. Instrument the funnel: invite → consent → connected → seeded → first subscription → first read opened.

## v2 feature list

- Connector support (email, calendar, docs — beyond harness-only signals)
- Decay detection proper (needs connector time-depth)
- Auto-pause/resume maintenance subscriptions based on `applied` signals (candidate)
- Opt-in `evidence` paraphrase for user self-review (candidate)

## Open items

1. Micro-learning generation quality — depth rubric wording, continuity mechanism (the week-one make-or-break for any first deployment)
2. Pressure-test the signal schema against a concrete scenario (e.g. a field engineer's first week on an unfamiliar customer stack)

*Closed: product name — settled as **HalfLife**.*
