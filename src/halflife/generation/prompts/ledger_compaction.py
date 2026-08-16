"""Compressing the oldest part of a coverage ledger.

The ledger is fed to every generation so an issue knows what not to re-explain.
It grows at roughly thirteen points an issue, so a daily subscription outgrows
what belongs in a prompt in about a fortnight. Dropping the oldest points would
let the series quietly re-cover ground it did last month; this compresses them
instead.

The output is still ledger entries, read by the same generation prompt under
the same rule — do not explain this again — so a claim only earns its place if
it is specific enough for a future issue to recognise the ground as covered.
"""

from __future__ import annotations

COMPACTION_PROMPT_VERSION = "1"

_SYSTEM = """\
You compress the older part of a coverage ledger for an ongoing micro-learning series.

The ledger records what the series has already established, one claim per line. It is given to
every new issue under a single instruction: do not explain any of this again. It has grown too
long to include in full, so the oldest entries must become fewer, broader claims.

What you produce is read by a writer who will never see the originals. A claim that is too vague
to recognise ground by — "covered connection handling", "discussed TLS" — is worse than useless,
because the writer cannot tell whether their subject is already taken and will re-explain it.
Every claim must stay specific enough to be recognised.

Rules:

* **Merge, do not summarise.** Several entries about one mechanism become one denser claim that
  carries the specifics. You are not writing an abstract of the series.
* **Keep the load-bearing particulars** — parameter names, thresholds, version numbers, failure
  modes, the direction of an effect. These are what make a claim recognisable. Lose them and the
  claim cannot do its job.
* **Drop nothing silently.** If several entries cannot be merged without losing what makes them
  distinct, keep them as separate claims. Returning more claims than the target is correct when
  the material genuinely does not compress; padding to hit the target is not.
* Write each claim as a standalone statement in the same register as the input: a thing the
  reader now knows, not a topic heading.
* Order claims so related ones sit together.
"""

_USER = """\
Series topic: {topic}

Compress these {count} ledger entries to roughly {target} claims.

{entries}\
"""


def build_system_prompt() -> str:
    return _SYSTEM


def build_user_prompt(*, topic: str, entries: list[str], target: int) -> str:
    return _USER.format(
        topic=topic,
        count=len(entries),
        target=target,
        entries="\n".join(f"- {entry}" for entry in entries),
    )
