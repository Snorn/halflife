# Rutherfords — Platform Design Doc (v0.2)

*Ideation output, August 2026. Status: HalfLife part-built, the rest concept only.*

HalfLife is the product this repository builds. Rutherfords is the platform it is one
instrument of, and everything about the platform below is unbuilt. The document is
product intent; [CLAUDE.md](CLAUDE.md) is what must hold in code, and where the two
disagree CLAUDE.md wins.

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

## Platform context — Rutherfords

*Added from an ideation session, 2026-08-21. This section describes a platform of which HalfLife
is one product. Nothing in it is built, and nothing in it changes the build order in
[CLAUDE.md](CLAUDE.md) — see "What this changed, and what it did not" at the end of the section.*

Rutherfords is the lab; the products are its instruments. **HalfLife** delivers regenerative
micro-learning where you work. **Geiger** detects skill decay through lightweight assessment.

The original sketch had both as heads on a shared **rubric engine** — parallel products, coupled
by a core. That is superseded: they are a **pipeline**. Geiger measures and emits signals;
HalfLife consumes them and treats. See "Geiger is the sensor, HalfLife is the treatment" below,
which is the settled position and changes where Geiger sits in the build order.

Geiger still has no code and no schema. What it now has is an output contract — the signal — and
that contract already exists in HalfLife.

### Design principles

- **Engine + heads.** One shared core (topic model, skill graph, depth calibration, user context)
  with per-application rubrics layered on top. Generation and assessment have different quality
  criteria — do not force them through one rubric.
- **Thick local agent.** All extraction and summarisation of harness conversations happens on the
  user's machine. Only content-free classifications ("insights, not content") are shipped to the
  control plane.
- **Boring technology.** Containers + Postgres + Redis. Provider-agnostic via 12-factor
  containers, not Kubernetes. Spend the complexity budget on the rubric engine, skill graph and
  agent; rent everything else.
- **Rubrics as data.** Rubrics are versioned in the database (prompt + validation), not hardcoded.
  Domain-specific rubrics (first target: continuous compliance) plug in at the gateway layer.

### System architecture

```mermaid
flowchart TB

subgraph USER["User's Machine"]
    direction TB
    HARNESS["AI Harnesses<br/>(Copilot / Claude Cowork / Amazon Q)"]
    AGENT["Rutherfords Agent (thick)<br/>local extraction & summarisation<br/>ships content-free classifications only"]
    HARNESS -->|conversations| AGENT
end

subgraph EDGE["Edge / Identity"]
    IDP["Hosted IdP (OIDC/SAML)<br/>WorkOS / Auth0 — SSO"]
    RMCP["Remote MCP Server<br/>streamable HTTP + OAuth<br/>in-harness delivery"]
end

subgraph CP["Control Plane — containers, provider-agnostic (Fly/Railway → ECS/Cloud Run)"]
    direction TB
    API["FastAPI Services<br/>tenant_id + Postgres RLS"]
    WORKERS["Async Workers (Celery/arq)<br/>content generation · scoring · signal processing"]
    GATEWAY["LLM Gateway (thin / LiteLLM)<br/>RUBRIC ENGINE<br/>rubrics versioned in DB<br/>generic core + per-app heads"]
    PG[("Postgres<br/>relational + pgvector + JSONB skill graph")]
    REDIS[("Redis<br/>queues & cache")]

    API --> REDIS
    REDIS --> WORKERS
    API --> PG
    WORKERS --> PG
    WORKERS --> GATEWAY
end

subgraph APPS["Applications (heads on the engine)"]
    HL["HalfLife<br/>subscriptions & micro-learnings<br/>regenerative learning"]
    GG["Geiger<br/>assessment & skill measurement<br/>(future: compliance evidence)"]
end

subgraph EXT["External"]
    LLM["LLM Providers<br/>(Anthropic / OpenAI / ...)"]
    MAIL["Email Notifications"]
end

AGENT -->|HTTPS + device token<br/>batched signals| API
HARNESS <-->|micro-learnings in-harness| RMCP
RMCP --> API
IDP -->|auth| API
API --> HL
API --> GG
HL --> GATEWAY
GG --> GATEWAY
GATEWAY --> LLM
WORKERS --> MAIL

subgraph FUTURE["Future (v2+)"]
    direction TB
    DR["Domain rubrics<br/>compliance head: provenance,<br/>versioned sources, audit records"]
    CH["Channels: voice · AR glasses"]
    CONN["Connectors beyond harness"]
end

GATEWAY -.-> DR
APPS -.-> CH
API -.-> CONN
```

### Key flows

1. **Signal capture.** The local agent reads harness conversations, performs extraction and
   summarisation locally, and POSTs batched content-free classifications to the control plane over
   HTTPS using a device token (pairing-code onboarding).
2. **Content generation.** Workers pull from the queue, call the rubric engine via the LLM
   gateway, and persist micro-learnings / assessment items to Postgres.
3. **Delivery.** The hosted remote MCP server (streamable HTTP + OAuth) serves micro-learnings and
   assessments back into whichever harness the user is in — harness-agnostic by design. Multiple
   harnesses (for example Claude Code and Claude Cowork) can run against the same instance
   concurrently.
4. **Identity.** All API access is authenticated via a hosted IdP (OIDC/SAML). Multi-tenancy is a
   `tenant_id` column with Postgres row-level security — the honest migration path to single-tenant
   deployments later.

### Marketing overview

Simplified for external audiences. The only technical claim it makes is the one that matters
commercially: *your content never leaves your machine — only insights do.*

That claim is true of extraction today and is not true of generation on the API path, which sends
the topic and the coverage ledger to Anthropic. On the harness path nothing leaves the machine but
the model call the harness was already making. Any use of this diagram needs to survive somebody
asking which path they are on.

```mermaid
flowchart LR

subgraph YOU["Where you work"]
    direction TB
    H["Your AI Assistant<br/>Copilot · Claude · Amazon Q"]
    A["Rutherfords Agent<br/>learns what you need to know<br/>🔒 your content never leaves your machine"]
    H --- A
end

subgraph RF["☢️ Rutherfords Platform"]
    direction TB
    ENGINE["Rubric Engine<br/>one core · many applications"]
    SG["Your Skill Graph<br/>maps what's strong,<br/>what's fading"]
    ENGINE --- SG
end

subgraph PRODUCTS["The Instruments"]
    direction TB
    HL["⚛️ HalfLife<br/>micro-learnings, delivered<br/>where you work —<br/>knowledge that regenerates"]
    GG["📟 Geiger<br/>lightweight assessment —<br/>detects skill decay<br/>before it matters"]
end

A -->|"insights, not content"| RF
RF --> HL
RF --> GG
HL -->|"learn"| H
GG -->|"measure"| H

FUT["Coming: voice · AR glasses ·<br/>continuous compliance"]
PRODUCTS -.-> FUT
```

### Geiger is the sensor, HalfLife is the treatment

Settled 2026-08-24. Geiger's output is a **signal**, and HalfLife is its consumer: a
self-assessment answered wrongly produces a suggested subscription. The two instruments are a
pipeline rather than two heads on a core, and the coupling between them is the signal schema that
already exists.

Three things follow, and the first is the reason to prefer this reading.

**It supplies the independent evidence nothing else can.** `depth_rubric.py` records that every
reader rating so far is *non-independent*: the rater curated the rubric through six versions, so
a run of "just right" cannot validate it. That note names two things that would be independent —
ambient signals, and other readers. An assessment failure is better than either, because it is
neither self-report nor opinion but a measurement against a known answer. It also sidesteps the
selection bias in **F2**: a reader can decline to log a session that went badly, and cannot
decline to have got a question wrong. This is the strongest available answer to **F1**, and it
arrives from the instrument that was supposed to be second in line.

**An item carries a depth, so a failure names a level as well as a subject.** Geiger items are
written against the same depth rubric, so failing one at depth 3 is not a topic hint — it is a
complete subscription spec, `topic, depth, minutes, cadence`, with the depth measured rather than
guessed. The calibrated asset does double duty, and the suggestion stops being "you might like to
read about this".

**`signal_type` needs an eighth verb, not a reused one.** `struggled` is the near miss: struggling
in conversation and failing a probe with a known correct answer are different observations, and
collapsing them discards the one that carries a measurement. Whatever it is called, it is the
only verb in the vocabulary whose truth does not depend on an agent's judgement of a
conversation.

One constraint has to be designed for rather than discovered. CLAUDE.md forbids a per-signal read
path, and a suggestion derived from a stored wrong answer is exactly that. The distinction that
keeps the rule intact is the one extraction already uses: **the recommendation comes from the
assessment just completed, in front of the reader — the signal is written for the record, not
read back to produce the advice.** Built that way the boundary holds. Built the obvious way it
becomes the per-signal read path this design forbids, arriving justified by the most sympathetic
case, which is how that path always arrives.

**Where this puts Geiger in the order.** As a sensor it needs no control plane, no engine
extraction and no server — a signal table, the depth rubric and a way to write items, all of
which exist or are one module away. That makes it reachable well before step 4, and the smallest
honest test of the whole idea is generating items from a series' existing coverage ledger: those
are claims a reader was told, at a known depth, on a known date, which is a position no standalone
assessment tool is in. Nothing is scheduled and nothing is scaffolded; what has changed is that
Geiger is no longer waiting on the engine/head split.

### What this changed, and what it did not

Consistent with what is already built or already written down: the thick local agent, content-free
classifications, `tenant_id` on every table, harness-agnostic delivery over MCP, the skill graph as
a deferred v2 surface, and topics normalised centrally rather than shipped to the agent. Postgres
RLS is a refinement of the tenancy rule rather than a change to it.

New, and unbuilt: Geiger, the engine/head split, the LLM gateway, Redis and async workers, the
hosted remote MCP server, and the domain-rubric plug-in point. Geiger's *relationship* to HalfLife
was revised on 2026-08-24 — see the section above — which moves it earlier without moving anything
else.

**Three things contradict what is currently written, and are open decisions rather than settled
ones.** They are listed here rather than merged, because each changes work already planned.

1. ~~**Kubernetes.**~~ **Settled 2026-08-21, in favour of this session's position.** Deployment
   is 12-factor containers on a provider-agnostic host — Fly or Railway first, ECS or Cloud Run
   later — and there is no Kubernetes, no Helm and no cluster. Step 4 of the build order in
   [CLAUDE.md](CLAUDE.md) was "Containerise → Helm → k3d → EKS" and is now containerisation
   alone. Kubernetes and Helm moved from the deferred list to the ruled-out one, which is a
   stronger statement: not "later" but "no". The architecture section below still carries the old
   position and is annotated where it does.
2. ~~**Rubrics as data.**~~ **Settled 2026-08-21, by scoping it.** The principle stands
   for *domain* rubrics and does not reach the core ones. The depth rubric and the generation
   prompts stay as versioned Python constants; a per-tenant domain rubric may be a database row
   when one exists. The two positions were never actually in conflict — one phrase was covering
   two different kinds of rubric. See the closed item for the reasoning, and for the condition any
   such row has to meet.
3. **Concurrent harnesses.** Key flow 3 states that multiple harnesses can run against one
   instance concurrently. That is asserted as a design property and is currently false in the
   code: see [issues #1–#4](https://github.com/Snorn/halflife/issues), which record that there is
   no dedupe on subscribe, no lease or conditional write between brief and record, and no way for
   a caller to detect that its state is stale. The remote MCP server makes this worse rather than
   better, because it turns two harnesses on one laptop into many harnesses across many machines.

## Architecture — HalfLife

*Predates the platform section above, and the control-plane bullet is superseded by it. The
Helm/K8s deployment target was dropped on 2026-08-21 in favour of 12-factor containers on a
provider-agnostic host. The bullet is left standing with this note rather than rewritten,
because the rest of it — what the control plane holds, and Postgres being enough for the graph
— is unaffected, and because a design doc that quietly reflows to match every decision stops
being a record of what was thought at the time.*

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
- `evidence` is **permanently null** — not "null for now". The column exists so the privacy stance is auditable, not as a staging area for a later opt-in. Enforced rather than intended: `repository.signals.assert_no_content` refuses any row that carries one.
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
- Geiger, the engine/head split, the LLM gateway, the hosted remote MCP server and
  domain rubrics — see [the platform section](#platform-context--rutherfords), which is
  where these are described rather than here, because they are platform-level and this
  list is HalfLife's

## Open items

1. Micro-learning generation quality — depth rubric wording, continuity mechanism (the week-one make-or-break for any first deployment)
2. Pressure-test the signal schema against a concrete scenario (e.g. a field engineer's first week on an unfamiliar customer stack)
3. **Concurrent harnesses.** The platform assumes many; the code supports one at a time.
   Tracked as [issues #1–#4](https://github.com/Snorn/halflife/issues).

*Closed: product name — settled as **HalfLife**.*

*Closed: where a rubric version lives — settled 2026-08-21 by scoping the question rather than answering it as put. "Rubrics as data" and "prompts as versioned constants" turned out not to be in conflict, because they are about two different kinds of rubric. A **core** rubric is calibration: the depth rubric went from 5/12 to 44/45 over six measured versions, the eval suite only compares runs because it can pin one, and the version recorded on every delivery is worth having because it names a commit somebody can read. That belongs in code. A **domain** rubric — the compliance head is the named case — is configuration: per-tenant, authored by someone with no deploy access, and useless if changing it needs a release. That belongs in data. One condition attaches to the data half: rubric rows must be append-only with the version in the row's identity, never updated in place, or a delivery's recorded version stops meaning anything. Nothing is built either way, and no table is added until there is a second tenant that needs one.*

*Closed: Kubernetes or not — settled 2026-08-21 against. Deployment is 12-factor containers on a provider-agnostic host, Fly or Railway first and ECS or Cloud Run later. The argument that decided it is the complexity-budget one: an orchestrator is a second system to keep alive, and a single-node control plane operated by one person has nothing for it to orchestrate. This removes a local cluster, a chart to maintain and a managed control plane to pay for, and it shortens the build order rather than lengthening it — which is the direction a decision taken before the work is worth taking. Revisit only on evidence of a scaling need, not on the general feeling that real platforms run on Kubernetes.*

*Closed: opt-in `evidence` paraphrase. It was listed here as a v2 candidate while CLAUDE.md forbade it by name, so the two source-of-truth documents disagreed about the same field. Settled against: an opt-in is how a permanently-null column stops being permanently null, and the consent it would rest on is the weakest part of the design — the person clicking it is the one with the least to lose and the most to gain from clicking. If self-review is wanted, it needs a mechanism that does not put content in the control plane, decided on the record.*
