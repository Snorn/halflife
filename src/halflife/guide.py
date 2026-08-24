"""The one explanation of how to use HalfLife.

Exposed twice — `halflife help` on the CLI and `halflife_help` over MCP — so a
harness can answer "how does this work?" without the user leaving their session.
Kept in one constant because two copies of usage instructions diverge within a
week, and the divergent one is always the one somebody reads.
"""

from __future__ import annotations

GUIDE = """\
# HalfLife

Short, depth-controlled reads that keep a skill from decaying. You subscribe to a topic at a
depth and a cadence; each issue knows what the earlier ones covered and may not re-explain it,
so a series accumulates instead of circling.

Your harness writes the issues using its own model. No API key is needed.

## The loop

1. **Subscribe** to a topic, choosing a depth (1-5), a length in minutes, and a cadence.
2. **Plan** the series once — an advisory arc, so it does not wander around the topic.
3. **Write** whatever is due. The tool hands over the prompt, the depth rubric, and everything
   already covered; your harness writes the issue and hands it back. A scheduled session can do
   this step for you — ask your harness to run the `halflife-deliver` skill daily, and issues
   wait in your inbox with no API key involved.
4. **Read** it.
5. **Give feedback** — on either of two axes. `too_basic` and `too_advanced` are about the
   *level*, and move the subscription's depth. `already_knew` and `wrong_subject` are about the
   *subject*: the level was right and the ground was wrong. Those leave depth alone and steer
   the next few issues somewhere else. This is the main way it learns to pitch itself for you.

   It is also what clears the issue from your inbox. Reading it does not, because nothing the
   tool can observe separates text being fetched from a person having read it — so the rating
   is the acknowledgement, and `just_right` is the honest one for "nothing to change".

Steps 3-5 are the daily habit. Steps 1-2 happen once per topic.

## Logging what you worked on

Separately from the loop, you can ask your harness to log a working session: *"log what I worked
on"*. It classifies the conversation it is already in and records subject names and one of seven
behavioural verbs — asked about it, explained it, applied it, struggled with it, and so on.

Nothing about the conversation itself goes anywhere. The tool is never sent the session; your
harness reads it, and what comes back is subjects and verbs, with no field in which anything else
could travel. It only ever runs when you ask.

What this is for is knowing which subjects are decaying without you having to tell it. Nothing
reads these signals back yet — there is no surface built on them.

## Things to say to your harness

- *"Subscribe me to Kubernetes admission controllers at depth 4, five minutes, daily."*
- *"Plan the Kubernetes admission controllers series."*
- *"Anything due in HalfLife?"*
- *"Write today's HalfLife issue."*
- *"Read me the latest issue."*
- *"That was too advanced."* — or *"that was pitched about right."*
- *"What has the SAP Web Dispatcher series covered so far?"*
- *"Log what I worked on."* — records subjects and verbs from this session, nothing else.
- *"What is HalfLife and how do I use it?"* — returns this guide.

## Choosing a depth

Depth sets **what you are assumed to already know**, not the length.

| depth | who it is written for |
|---|---|
| 1 | You have heard the term and cannot place it. What it is, what problem it solves. |
| 2 | You could follow a conversation about it. Vocabulary, the moving parts, how they relate. |
| 3 | You have done this before. Real configuration, decision points, what commonly breaks. |
| 4 | You are competent and want what experience teaches. Interactions, second-order effects. |
| 5 | You are at the edge of the published material. Internals, edge cases, version specifics. |

**A depth-1 series finishes.** Orientation is a finite amount of material, so a depth-1
subscription runs to three issues and then reports itself complete rather than padding. That is
measured: the fourth issue drifts several levels deeper because the ground is gone. Rate an issue
`too_basic` to move it to depth 2 and carry on, or unsubscribe. Depths 2 and above do not run
out and are not capped.

If issues feel wrong, do not re-subscribe — give feedback. Say `too_basic` or `too_advanced`
when the level is off, and `already_knew` or `wrong_subject` when the level was fine but the
material was not what you needed.

**Flavour** is `learning` (new ground) or `maintaining` (a refresher on something you already
know well, which assumes competence and leads with what decays first). Cadence defaults to
daily; `weekly` suits maintaining series, and `hourly` exists for cramming.

## Tools your harness has

| tool | what it does |
|---|---|
| `halflife_subscribe` / `halflife_list_subscriptions` | create and list subscriptions |
| `halflife_plan_brief` / `halflife_record_plan` | draw the series arc, once per subscription |
| `halflife_list_due` | what is due now |
| `halflife_next_brief` | the prompt, depth, word budget, ledger and open threads |
| `halflife_record_issue` | save a written issue and advance the series |
| `halflife_pending_reads` / `halflife_read` | what is waiting, and its text |
| `halflife_feedback` | `too_basic` / `just_right` / `too_advanced` (level), `already_knew` / `wrong_subject` (subject) |
| `halflife_compaction_brief` / `halflife_record_compaction` | compress the ledger when it grows too long |
| `halflife_add_thread` | tell a series it missed something you want covered |
| `halflife_extraction_brief` / `halflife_record_signals` | classify a session into subjects and verbs, when you ask |
| `halflife_help` | this guide |

## Commands

Run from a terminal. These need no API key.

| command | what it does |
|---|---|
| `halflife init` | create or upgrade the database. Once per machine, and again after an update adds a migration — anything that touches the database will tell you when. |
| `halflife help` | this guide |
| `halflife subscribe "<topic>, <depth>, <mins>, <freq>"` | create a subscription from the terminal instead of asking your harness |
| `halflife ls` | subscriptions, issue counts, next due time |
| `halflife inbox` | issues waiting on you: unseen, or seen and not yet rated |
| `halflife read [id\\|latest]` | read an issue. Rating it, not reading it, clears the inbox |
| `halflife feedback <id> <verdict>` | `too-basic`, `just-right`, `too-advanced` move depth; `already-knew`, `wrong-subject` move the subject |
| `halflife flavour <sub> learning\|maintaining` | switch between building a skill up and keeping one alive |
| `halflife thread <sub> "<text>"` | tell a series it missed something you want covered |
| `halflife duration <sub> <minutes>` | how long an issue should take to read |
| `halflife frequency <sub> 1h\|1d\|1w` | how often an issue is due |
| `halflife series <sub>` | the plan, the coverage ledger, and open threads. `--full` includes compacted entries |
| `halflife cost` | spend to date and projected monthly run rate |
| `halflife pause <sub>` / `halflife resume <sub>` | stop and restart delivery, keeping the series |
| `halflife unsubscribe <sub>` | delete a subscription and everything it has delivered. Irreversible |

Ids can be any unambiguous prefix — the eight characters shown by `ls` are enough.

`unsubscribe` is deliberately not available to your harness: everything else is additive or
reversible, and nothing needs a model able to delete your reading history.

## If you have an Anthropic API key

Optional, and only worth it for one thing: generation on a pinned model, which is what makes
output comparable between issues and is required for the evals in `evals/`. (`halflife run-due`
also generates unattended, but a scheduled harness session does that too, without a key.) Without
a key, everything above still works — your harness does the generating.
"""


def guide_text() -> str:
    return GUIDE
