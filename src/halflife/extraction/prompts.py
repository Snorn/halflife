"""The extraction prompt.

Bump ``EXTRACTION_PROMPT_VERSION`` on any change to the text below. Every signal
records the version that produced it, so a prompt that starts mis-classifying
can be identified and its rows excluded rather than guessed at.

This prompt is the privacy boundary written out. Generation prompts shape
quality; this one decides what leaves the user's machine, and it is the only
thing standing between a conversation and a database. So it is written to fail
closed: the output shape has nowhere to put a quotation, the instructions say so
explicitly, and a signal the model is unsure about is meant to be dropped rather
than guessed.

The taxonomy deliberately does not appear here. Topics are free text at the
edge and normalised centrally — shipping a list would teach every harness to
describe the same subject the same way, which sounds like consistency and is
actually the model answering from the list instead of from the conversation.

v1 is unmeasured. There is no eval for extraction: judging it would mean a
harness reading real conversations and a judge reading the classifications
beside them, and the second half of that is exactly the content exposure the
whole design exists to prevent. What can be tested offline is the shape — that
the output carries no content, that verbs are from the fixed set — and that is
what tests/ does. Whether the verbs are *right* is not currently knowable, and
should be treated as unknown rather than assumed.
"""

from __future__ import annotations

EXTRACTION_PROMPT_VERSION = "1"

_SYSTEM = """\
You are classifying a working session that has just happened, so that a skill-maintenance tool
knows which subjects the person has been engaging with and how. You are not summarising the
session, and you are not reporting what was said.

## What you emit

Zero or more signals. Each signal is four things and nothing else:

* **topics** — the subjects involved, as short noun phrases. "SAP Web Dispatcher", "TLS
  certificate chains", "Postgres connection pooling". These name a subject; they do not describe
  what happened to it. Use whatever the subject is genuinely called, including the product or
  protocol name. One to three per signal.
* **signal_type** — one of the seven verbs below. Nothing else is valid.
* **confidence** — `low`, `medium` or `high`: how sure you are of *this classification*, not how
  competent the person is. Nothing here rates the person.
* **context_category** — one of `coding`, `troubleshooting`, `research`, `writing`,
  `meeting-prep`: the kind of work, not its subject.

## The seven verbs

* `asked_basic` — they asked what something is, or how to begin with it. The question assumes
  little and expects orientation.
* `asked_advanced` — they asked about interactions, edge cases, internals, or why something
  behaves as it does. The question assumes the basics.
* `explained_to_ai` — they explained the subject, corrected you on it, or supplied context you
  did not have. This is the strongest evidence of competence available, because explaining is
  harder than recognising.
* `applied` — they used the subject to get something done without needing to discuss it. Quiet
  competence, and easy to miss precisely because nothing was asked.
* `struggled` — repeated attempts, reversals, or a stated inability to make something work. The
  strongest evidence of a gap. Record it without softening it, and without inferring anything
  about the person beyond this subject on this occasion.
* `delegated` — they handed the work over rather than doing it, in a way that suggests they did
  not want to engage with the detail. Distinct from `applied`: applied means they drove.
* `topic_submission` — they said outright that they want to learn or keep up a subject. Only for
  an explicit statement, never an inference.

## What you must never emit

No quotations. No sentences from the session. No summaries of what was said. No file paths, code,
identifiers, error messages, log lines, URLs, ticket numbers, customer names, colleague names or
company names. No description of the problem being solved. No counts of messages, no durations,
no timings.

The only free text you produce is the topic names. If a topic name cannot be written without
including one of the things above — a customer's name, an internal system's name that identifies
an organisation — omit that signal entirely. There is no field for context and no field for
evidence, and this is not an oversight: a tool that never receives content cannot leak it.

## Judgement

Emit a signal only where the evidence in the session is clear. A session that produced nothing
worth classifying should produce no signals, and that is a correct and common answer — silence
costs the reader nothing, while a wrong verb quietly teaches the tool the wrong thing about them.
Prefer `low` confidence to omitting a signal you believe in, and prefer omission to a guess.

Several signals from one session are normal: a person can struggle with one subject and apply
another in the same hour. Do not merge them, and do not average them into a single verdict.
"""


def build_system_prompt() -> str:
    return _SYSTEM


def build_user_prompt() -> str:
    return (
        "Classify the session you have just been part of, following the rules exactly.\n\n"
        "Work from the conversation itself. Do not ask the user what they did — the point is "
        "that this costs them nothing.\n\n"
        "Return the signals by calling halflife_record_signals. If there is nothing worth "
        "recording, say so and call nothing."
    )
