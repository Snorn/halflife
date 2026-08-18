# HalfLife

**[snorn.github.io/halflife](https://snorn.github.io/halflife/)** — the introduction, including
five pieces on one topic written at five different depths, so you can see what the depth
parameter actually does before reading a line of this.

Professional skill *maintenance*. Every skill has a half-life; this tops yours back up before it
runs down. Most learning tools help you acquire something new — this one helps you keep what you
already learned.

You subscribe to a topic at a depth and a cadence, and it writes you a short, single-sitting read
on a schedule. Each issue knows what the previous ones covered and is forbidden from re-explaining
it, so a series accumulates instead of circling.

**It runs inside the AI harness you already use** — Claude Code, Claude Cowork, or anything else
that speaks MCP — and needs no API key of its own. Your harness's model writes the issues;
HalfLife holds the depth rubric, the schedule and the memory of what has already been said.

> **Status: early, and honest about it.** The generation engine and the harness integration are
> built and measured. There is no server, no multi-user support and no deployment story — those
> are deliberately later steps. It is useful today if you want a daily read on a topic you are
> keeping alive; it is not yet a product.

## What makes it different from a prompt

Two mechanisms, both measured rather than assumed:

**A depth rubric.** Depth 1–5 sets *what the reader is assumed to already know*, not the word
count. A depth-2 and a depth-4 piece on the same topic should be disjoint, not one a longer
version of the other. The rubric is a versioned constant, and
[its own source file](src/halflife/generation/prompts/depth_rubric.py) records what each revision
changed, what it measured, and where it still fails.

**A coverage ledger.** Every issue returns the claims it established; these accumulate and are fed
into the next generation as ground that may be referred to but not taught again. When the ledger
outgrows a prompt, the oldest entries are compressed into denser claims rather than dropped.

## Requirements

- Python 3.11+
- An MCP-capable harness (Claude Code, Claude Cowork, …)

No Anthropic API key is required. One is only needed for the optional API path in
[Appendix A](#appendix-a-generating-via-the-api).

## Install

```bash
git clone https://github.com/Snorn/halflife.git && cd halflife
```

```bash
python -m venv .venv
```

```bash
.venv/bin/python -m pip install -e ".[dev]"      # Windows: .venv\Scripts\python.exe
```

```bash
.venv/bin/python -m pytest -q
```

The test suite is fully offline, so it passes before any harness wiring or credentials exist. If
it goes green, the install is sound. Then create the database:

```bash
.venv/bin/halflife init
```

## Register it with your harness

You need the absolute path to the installed `halflife-mcp` on *your* machine. Print it:

```bash
.venv/bin/python scripts/mcp_doctor.py
```

Check 2 of its output is the path to paste. Then, in your harness's MCP configuration:

```json
{
  "mcpServers": {
    "halflife": { "command": "PASTE_THE_PATH_FROM_CHECK_2_HERE" }
  }
}
```

**That value is a placeholder, not a working default** — the single most common setup failure is
leaving it unedited, and a harness reports it the same way it reports every other attach failure.
On Windows the path needs doubled backslashes:
`C:\\dev\\halflife\\.venv\\Scripts\\halflife-mcp.exe`.

Then **restart the harness** — MCP servers load at startup, not when the config changes.

If it will not attach, `scripts/mcp_doctor.py` runs the same checks the harness does and stops at
the first failure, including whether the configured command path actually exists.

## Daily use

Everything from here happens in your harness, in plain language. Ask it to subscribe you to a
topic, plan the series, and write what is due — it has tools for each step and follows the
sequence on its own.

Subscriptions are created from shorthand: `topic, depth, duration, frequency, flavour`, where
everything after the topic is optional. Depth is 1–5, duration is minutes, frequency is
`1h`/`1d`/`1w`, and flavour is `learning` (new ground) or `maintaining` (refresher on a skill you
already have). Frequency defaults to daily — hourly exists for cramming and has to be asked for.
So *"subscribe me to sap web dispatcher at depth 4, five minutes, daily"* is enough.

The tools it uses:

| tool | what it does |
|---|---|
| `halflife_subscribe` / `halflife_list_subscriptions` | create and list subscriptions |
| `halflife_plan_brief` / `halflife_record_plan` | sketch a new series' arc — once per subscription |
| `halflife_list_due` | what is due now |
| `halflife_next_brief` | the prompt, depth, word budget, ledger, open threads and reader feedback |
| `halflife_record_issue` | saves the issue and which plan entry it took, updates the ledger, advances the schedule |
| `halflife_pending_reads` / `halflife_read` | what is waiting, and its text |
| `halflife_feedback` | `too_basic` / `just_right` / `too_advanced` move depth; `already_knew` / `wrong_subject` move the subject |
| `halflife_compaction_brief` / `halflife_record_compaction` | compress the ledger when it outgrows a prompt |
| `halflife_help` | the built-in guide: the loop, depths, and everything above |

You do not have to remember any of this. Ask your harness *"what is HalfLife and how do I use
it?"* and it will call `halflife_help`, which explains the loop, what each depth means, and what
to say next.

Nothing here spends anything with Anthropic: the model is the one your harness already runs.
`halflife init` is the only step that has to come from the CLI, because it runs schema migrations
— which is not something a model-invoked tool should be able to do.

**What that costs you.** Nothing generates unless a session is open — there is no unattended
delivery. And the model is whatever your harness runs, so quality is neither pinned nor comparable
between installs. Every delivery records a `source` of `api` or `harness`, and `model_id` is left
null rather than guessed when the harness does not report one, so the distinction survives into
any later analysis.

## Managing subscriptions from the CLI

These need no API key and work regardless of how issues were generated:

| Command | What it does |
|---|---|
| `help` | The built-in guide: the loop, depths, tools and commands. Works before `init`. |
| `ls` | Subscriptions, with issue counts and next due time. |
| `inbox` / `read [id\|latest]` | What is unread; read it. |
| `feedback <delivery> <verdict>` | Two axes: `too-basic` / `just-right` / `too-advanced` nudge the subscription's depth; `already-knew` / `wrong-subject` leave depth alone and tell the next few issues to take different ground. |
| `series <sub>` | The continuity state: plan, coverage ledger, open threads. `--full` includes compacted entries. |
| `cost` | Spend to date per subscription, and the projected monthly run rate. |
| `pause` / `resume <sub>` | Stop and restart delivery, keeping the series. |
| `unsubscribe <sub>` | Delete a subscription, its series and every issue it delivered. Irreversible; confirms first, `--yes` to skip. |

Ids can be given as any unambiguous prefix, so the eight characters shown in `ls` are enough.

Deletion is deliberately **not** exposed over MCP — everything else in the tool is additive or
reversible, and there is no reason a model needs to remove your reading history.

## How a series stays coherent

Four pieces of state, rather than one prose summary:

* a **plan** — an advisory arc drawn once per subscription, so the series does not random-walk
  around the topic;
* a **coverage ledger** — append-only, one short claim per line, fed into every generation as
  ground that may be referred to but not re-explained;
* **open threads** — things an issue deliberately deferred, which the next one picks up or drops;
* **your feedback** — see below.

Each generation returns the body *and* the updated bookkeeping together, so the ledger cannot
drift from what was actually written. `halflife series <sub>` shows the first three.

The plan is annotated rather than merely listed. Each generation reports which plan entry it
actually covered, so entries show as written, as struck out where you rejected them, or as
untouched — and an entry the series skipped is visibly different from one it covered. Deviating
from the plan is allowed, which is exactly why position in the series is not evidence of what was
covered.

## Feedback has two axes

Saying an issue missed is not the same as saying it was pitched wrong, and collapsing the two
loses the more useful half.

* **Level** — `too_basic` and `too_advanced` move the subscription's depth one step, clamped to
  1–5. This is the main way it learns to pitch itself for you.
* **Subject** — `already_knew` and `wrong_subject` say the level was right and the ground was
  wrong. They leave depth alone. Instead the rejection reaches the next generations directly:
  recent ones are spelled out, and the rejected plan entry stays struck out for the life of the
  series.

Unlike the depth rubric and the coverage ledger, this is not measured yet. It is a mechanism with
a rationale, not a result.

## Design and constraints

[The design doc](regenerative-learning-platform-design.md) is the product rationale;
[CLAUDE.md](CLAUDE.md) is the set of constraints that must hold in code. Two are worth knowing
before contributing:

**The build order is deliberate.** Generation engine → MCP server → API and Postgres →
containerisation. Kubernetes, Helm, SSO and tenancy enforcement are explicitly *not* to be
scaffolded ahead of time, not even as placeholders.

**The privacy boundary is non-negotiable.** When the agent half is built, the control plane sees
classifications and never content — an `evidence` field exists in the signal schema and is
permanently null, present so the stance is auditable. No signals are written yet, but the schema
is fixed now.

## Contributing

Issues and pull requests welcome. Two things to know:

- `tests/` must stay deterministic and offline. Anything that asserts on model output belongs in
  `evals/`, which costs money to run.
- Prompts live in `generation/prompts/` as versioned constants. Changing one means bumping its
  version, because every generated issue records the versions that produced it — otherwise
  quality changes cannot be attributed.

## Licence

[Apache-2.0](LICENSE).

---

# Appendix A: generating via the API

The harness path above is the default. HalfLife can also generate issues itself by calling the
Anthropic API directly, which buys two things the harness path cannot give you:

- **Unattended delivery.** `run-due` generates on a schedule with nobody present.
- **A pinned model and effort**, which is the only way output is comparable across deliveries —
  and therefore the only path on which the evals mean anything.

This is how the prompts are tuned. It requires an API key with credit; an API key is separate
from a Claude.ai subscription, which does **not** include API access.

Credentials resolve the way the Anthropic SDK expects — `ANTHROPIC_API_KEY`,
`ANTHROPIC_AUTH_TOKEN`, or an `ant auth login` profile. Set `HALFLIFE_ANTHROPIC_API_KEY` only to
force a specific key. See [.env.example](.env.example).

| Command | What it does |
|---|---|
| `subscribe "<shorthand>"` | Sketches the series arc via the API. Without a key it warns and creates the subscription unplanned; `--no-plan` skips the attempt. |
| `run-due` | Generate an issue for everything that is due. `--dry-run` to look first. |
| `generate <sub>` | Generate now, ignoring the schedule. |

## What it costs

Measured, not estimated. At the default `effort=medium` an API call costs **about $0.08**, so a
daily subscription runs to roughly $2.50 a month. Most of the bill is output tokens, because
thinking bills as output.

`effort` is the dominant cost lever, and the intuitive setting is the wrong one: two depth-eval
runs at `medium` each scored **11/12** against `high`'s 9/12, at roughly 40% of the price. Higher
effort explores more before answering, which is not what a tightly-rubric-constrained task wants.
Measure before raising it.

`halflife cost` reports spend from the tokens recorded on each delivery. Harness-written issues
are excluded rather than costed — whatever they cost was paid inside the tool you were already
running.

## Evals

```bash
python evals/run_evals.py depth
```

A depth run is 28 API calls (~$2 at medium); tuning the rubric across three revisions cost around
$20. Every run prints what it spent. The `distance` suite judges output already on disk, so a
prompt revision can be compared against an older run without regenerating either arm. See [evals/](evals/README.md) — that is where you find out
whether the depth rubric actually holds, and whether issue 6 knows what issue 1 said.

Nothing in `tests/` touches the network:

```bash
.venv/bin/python -m pytest -q
```

# Appendix B: schema changes

Alembic owns the schema; there is no `create_all` path. After pulling a change that adds a
migration, re-run `halflife init` — it is idempotent and reports when there was nothing to do:

```bash
.venv/bin/halflife init
```

```bash
.venv/bin/alembic revision --autogenerate -m "what changed"
```

```bash
.venv/bin/alembic upgrade head
```
