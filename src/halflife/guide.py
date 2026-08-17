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
   already covered; your harness writes the issue and hands it back.
4. **Read** it.
5. **Give feedback** — `too_basic` or `too_advanced` moves the subscription's depth for future
   issues. This is the main way it learns to pitch itself correctly for you.

Steps 3-5 are the daily habit. Steps 1-2 happen once per topic.

## Things to say to your harness

- *"Subscribe me to Kubernetes admission controllers at depth 4, five minutes, daily."*
- *"Plan the Kubernetes admission controllers series."*
- *"Anything due in HalfLife?"*
- *"Write today's HalfLife issue."*
- *"Read me the latest issue."*
- *"That was too advanced."* — or *"that was pitched about right."*
- *"What has the SAP Web Dispatcher series covered so far?"*
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

If issues feel wrong, do not re-subscribe — give feedback and let the depth move.

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
| `halflife_feedback` | `too_basic` / `just_right` / `too_advanced` |
| `halflife_compaction_brief` / `halflife_record_compaction` | compress the ledger when it grows too long |
| `halflife_help` | this guide |

## Commands

Run from a terminal. These need no API key.

| command | what it does |
|---|---|
| `halflife init` | create or upgrade the database. Required once per machine. |
| `halflife help` | this guide |
| `halflife ls` | subscriptions, issue counts, next due time |
| `halflife inbox` | issues written but not yet read |
| `halflife read [id\\|latest]` | read an issue and mark it read |
| `halflife feedback <id> too-basic\\|just-right\\|too-advanced` | adjust future depth |
| `halflife series <sub>` | the plan, the coverage ledger, and open threads. `--full` includes compacted entries |
| `halflife cost` | spend to date and projected monthly run rate |
| `halflife pause` / `resume <sub>` | stop and restart delivery, keeping the series |
| `halflife unsubscribe <sub>` | delete a subscription and everything it has delivered. Irreversible |

Ids can be any unambiguous prefix — the eight characters shown by `ls` are enough.

`unsubscribe` is deliberately not available to your harness: everything else is additive or
reversible, and nothing needs a model able to delete your reading history.

## If you have an Anthropic API key

Optional, and only worth it for two things: `halflife run-due` generates unattended, without a
session open; and generation runs on a pinned model, which is what makes output comparable
between issues and is required for the evals in `evals/`. Without a key, everything above still
works — your harness does the generating.
"""


def guide_text() -> str:
    return GUIDE
