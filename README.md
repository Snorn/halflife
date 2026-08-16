# HalfLife

Professional skill *maintenance*. Every skill has a half-life; this tops yours back up before it
runs down. Most learning tools help you acquire something new — this one helps you keep what you
already learned.

You subscribe to a topic at a depth and a cadence, and it writes you a short, single-sitting read
on a schedule. Each issue knows what the previous ones covered and is forbidden from re-explaining
it, so a series accumulates instead of circling.

> **Status: early, and honest about it.** This is step one of four — the generation engine,
> standalone, against SQLite, driven from a CLI. There is no server, no MCP integration, no
> deployment story, and no multi-user anything. Those are deliberately not built yet. It is
> useful today if you want a daily read on a topic you're keeping alive; it is not a product.

## What makes it different from a prompt

Two mechanisms, both of which have been measured rather than assumed:

**A depth rubric.** Depth 1–5 sets *what the reader is assumed to already know*, not the word
count. A depth-2 and a depth-4 piece on the same topic should be disjoint, not one a longer
version of the other. The rubric is a versioned constant, and
[its own source file](src/halflife/generation/prompts/depth_rubric.py) records what each revision
changed, what it measured, and where it still fails.

**A coverage ledger.** Every issue returns the claims it established; these accumulate and are fed
back into the next generation as ground that may be referred to but not taught again. When the
ledger outgrows a prompt, the oldest entries are compressed into denser claims rather than
dropped.

## Requirements

- Python 3.11+
- An Anthropic API key with credit. Generation calls `claude-opus-5` directly — an API key is
  separate from a Claude.ai subscription, which does **not** include API access.

## Setup

```bash
python -m venv .venv
```

```bash
.venv/bin/python -m pip install -e ".[dev]"      # Windows: .venv\Scripts\python.exe
```

```bash
.venv/bin/halflife init
```

Credentials resolve the way the Anthropic SDK expects — `ANTHROPIC_API_KEY`,
`ANTHROPIC_AUTH_TOKEN`, or an `ant auth login` profile. Set `HALFLIFE_ANTHROPIC_API_KEY` only to
force a specific key. See [.env.example](.env.example).

## What it costs

Measured, not estimated. At the default `effort=medium`, an API call costs **about $0.08** — so a
daily subscription runs to roughly $2.50 a month. Most of the bill is output tokens, because
thinking bills as output.

`effort` is the dominant cost lever, and the intuitive setting is the wrong one: two depth-eval
runs at `medium` each scored **11/12** against `high`'s 9/12, at roughly 40% of the price. Higher
effort explores more before answering, which is not what a tightly-rubric-constrained task wants.
Measure before raising it.

The evals in [evals/](evals/README.md) are the expensive part: a depth run is 28 API calls (~$2 at
medium), and tuning the rubric across three revisions cost around $20. Every eval run prints what
it spent. Nothing in `tests/` touches the network.

## Daily use

```bash
halflife subscribe "sap web dispatcher, 3, 5, 1d"
halflife run-due
halflife read latest
halflife feedback 4f2a1c9b too-advanced
```

Shorthand is `topic, depth, duration, frequency, flavour`; everything after the topic is
optional. Depth is 1–5, duration is minutes, frequency is `1h`/`1d`/`1w`, and flavour is
`learning` (new ground) or `maintaining` (refresher on a skill you already have). Frequency
defaults to daily — hourly exists for cramming and has to be asked for.

| Command | |
|---|---|
| `subscribe "<shorthand>"` | Create a subscription and sketch its arc. `--no-plan` skips the arc. |
| `ls` | Subscriptions, with issue counts and next due time. |
| `run-due` | Generate an issue for everything that is due. `--dry-run` to look first. |
| `generate <sub>` | Generate now, ignoring the schedule. |
| `inbox` / `read [id\|latest]` | What is unread; read it. |
| `feedback <delivery> too-basic\|just-right\|too-advanced` | Nudges the subscription's depth. |
| `series <sub>` | The continuity state: plan, coverage ledger, open threads. |
| `pause` / `resume <sub>` | Stop and restart delivery, keeping the series. |
| `unsubscribe <sub>` | Delete a subscription, its series and every issue it delivered. Irreversible; confirms first, `--yes` to skip. |

Ids can be given as any unambiguous prefix, so the eight characters shown in `ls` are enough.

## How a series stays coherent

Three pieces of state, rather than one prose summary:

* a **plan** — an advisory arc generated once at subscribe time, so the series does not
  random-walk around the topic;
* a **coverage ledger** — append-only, one short claim per line, fed into every generation as
  ground that may be referred to but not re-explained;
* **open threads** — things an issue deliberately deferred, which the next one picks up or drops.

Each generation is a single API call that returns the body *and* the updated bookkeeping, so the
ledger cannot drift from what was actually written. `halflife series <sub>` shows all three.

## Tests and evals

```bash
.venv\Scripts\python.exe -m pytest          # offline, deterministic
python evals/run_evals.py depth             # costs tokens
```

`tests/` never touches the network. Anything that judges real model output lives in
[evals/](evals/README.md) — that is where you find out whether the depth rubric actually holds
and whether issue 6 knows what issue 1 said.

## Schema changes

Alembic owns the schema; there is no `create_all` path.

```bash
.venv/bin/alembic revision --autogenerate -m "what changed"
```

```bash
.venv/bin/alembic upgrade head
```

## Using it inside a harness (no API key)

`halflife-mcp` is an MCP server that inverts the generation flow: instead of HalfLife calling a
model, your harness calls HalfLife. It hands out the assembled prompt, your harness's own model
writes the issue, and it takes the result back and does the bookkeeping.

That means **it works with no Anthropic API key at all** — the model is the one you already have
approved.

To register it, you need the absolute path to the installed `halflife-mcp` on *your* machine.
Print it:

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
On Windows the path needs doubled backslashes: `C:\\dev\\halflife\\.venv\\Scripts\\halflife-mcp.exe`.

Then **restart the harness** — MCP servers are loaded at startup, not when the config changes.

If it will not attach, `scripts/mcp_doctor.py` runs the same checks the harness does and stops at
the first failure, including whether the configured command path actually exists.

Then ask your harness to deliver today's read. The loop it follows:

| tool | |
|---|---|
| `halflife_plan_brief` / `halflife_record_plan` | sketch a new series' arc — worth doing once per subscription |
| `halflife_list_due` | what's due now |
| `halflife_next_brief` | the prompt, depth, word budget, ledger and open threads |
| `halflife_record_issue` | saves the written issue, updates the ledger, advances the schedule |
| `halflife_pending_reads` / `halflife_read` | what's waiting, and its text |
| `halflife_feedback` | `too_basic` / `just_right` / `too_advanced`, adjusts future depth |
| `halflife_compaction_brief` / `halflife_record_compaction` | compress the ledger when it outgrows a prompt |

**What this costs you.** Nothing generates unless a session is open — there is no unattended
delivery. And the model is whatever your harness runs, so quality is neither pinned nor comparable
between installs. Every delivery records a `source` of `api` or `harness`, and `model_id` is left
null rather than guessed when the harness doesn't report one, so this distinction survives into
any later analysis.

The API path remains for evals and prompt tuning, where a pinned model is the whole point.

## Design and constraints

[The design doc](regenerative-learning-platform-design.md) is the product rationale;
[CLAUDE.md](CLAUDE.md) is the set of constraints that must hold in code. Two are worth knowing
before contributing:

**The build order is deliberate.** Generation engine → MCP server → API and Postgres →
containerisation. Kubernetes, Helm, SSO and tenancy enforcement are explicitly *not* to be
scaffolded ahead of time, not even as placeholders.

**The privacy boundary is non-negotiable.** When the agent half is built, the control plane sees
classifications and never content — an `evidence` field exists in the signal schema and is
permanently null, present so the stance is auditable. Step 1 writes no signals at all, but the
schema is fixed now.

## Contributing

Issues and pull requests welcome. Two things to know:

- `tests/` must stay deterministic and offline. Anything that asserts on model output belongs in
  `evals/`, which costs money to run.
- Prompts live in `generation/prompts/` as versioned constants. Changing one means bumping its
  version, because every generated issue records the versions that produced it — otherwise
  quality changes can't be attributed.

## Licence

[Apache-2.0](LICENSE).
