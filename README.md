# HalfLife

Professional skill maintenance. Every skill has a half-life; this tops yours back up before it
runs down.

**This repo is step 1 of four:** the micro-learning generation engine, standalone, against SQLite,
driven from a CLI. The MCP server, the API, and the deployment story come later and deliberately
do not exist yet. See [CLAUDE.md](CLAUDE.md) for the build order and the constraints, and
[the design doc](regenerative-learning-platform-design.md) for the product.

## Setup

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\halflife.exe init
```

Generation calls the Anthropic API. The SDK finds credentials on its own from
`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, or an `ant auth login` profile — set
`HALFLIFE_ANTHROPIC_API_KEY` only if you need to force a specific key. See
[.env.example](.env.example) for the rest.

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
| `pause` / `resume <sub>` | |

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
.venv\Scripts\alembic.exe revision --autogenerate -m "what changed"
.venv\Scripts\alembic.exe upgrade head
```
