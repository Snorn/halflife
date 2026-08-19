"""The product name is spelled HalfLife, and stays that way.

Casing drifts one paragraph at a time, and by the time anybody notices, the
wrong spelling is in a paragraph nobody wants to re-read. This is cheap enough
to run on every commit, so the drift never starts.

Two spellings are deliberately not the product name and must survive untouched:

* **code identifiers** — the ``halflife`` command, ``halflife-mcp``, the
  ``halflife_*`` MCP tools, ``HALFLIFE_*`` environment variables, import paths
  and the repository URL. These are API surface; recasing them breaks things.
* **the physics term** — "every skill has a half-life" is a different word that
  happens to have lent the product its name. It is lowercase and hyphenated.

So the check strips anything that could hold an identifier — fenced blocks,
inline code, HTML markup and URLs — and then insists that whatever prose is
left spells it either ``HalfLife`` or ``half-life``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

DOCS = [
    "README.md",
    "CLAUDE.md",
    "NOTICE",
    "docs/index.html",
    "evals/README.md",
    "regenerative-learning-platform-design.md",
]

# Anything that can legitimately carry a lowercase identifier. Order matters:
# element contents go before the generic tag strip, or the tags vanish and
# leave their text behind. The slash rule is deliberately broad — a token with
# a slash in it is a path, a URL or a markdown link target, never prose. The
# last four of these earned their place by producing a false positive on the
# first run against the real documents.
_STRIP = [
    re.compile(r"<script\b.*?</script>", re.S | re.I),
    re.compile(r"<style\b.*?</style>", re.S | re.I),
    re.compile(r"<pre\b.*?</pre>", re.S | re.I),
    re.compile(r"```.*?```", re.S),
    re.compile(r"`[^`\n]*`"),
    re.compile(r"\]\([^)]*\)"),
    re.compile(r"<[^>]+>", re.S),
    re.compile(r"https?://\S+"),
    re.compile(r"\S*[/\\]\S*"),
]

# Every way of writing the name, so a new variant is caught rather than missed.
_ANY_SPELLING = re.compile(r"\bhalf[\s‑-]?life\b", re.I)

CORRECT_NAME = "HalfLife"
PHYSICS_TERM = "half-life"


def _prose(text: str) -> str:
    for pattern in _STRIP:
        text = pattern.sub(" ", text)
    return text


def _offences(text: str) -> list[str]:
    return [
        found
        for found in _ANY_SPELLING.findall(_prose(text))
        if found not in (CORRECT_NAME, PHYSICS_TERM)
    ]


@pytest.mark.parametrize("relative", DOCS)
def test_the_product_name_is_camel_case(relative: str) -> None:
    path = ROOT / relative
    assert path.exists(), f"{relative} is in the guarded list but missing"

    offences = _offences(path.read_text(encoding="utf-8"))

    assert not offences, (
        f"{relative} spells the product name {sorted(set(offences))}. "
        f"It is {CORRECT_NAME} in prose; {PHYSICS_TERM} is the physics term, "
        "and identifiers belong in code spans."
    )


def test_the_check_would_catch_a_wrong_spelling() -> None:
    """A guard nobody has seen fail is a guard nobody knows works."""
    assert _offences("Halflife writes you a read.") == ["Halflife"]
    assert _offences("halflife writes you a read.") == ["halflife"]
    assert _offences("Half-Life writes you a read.") == ["Half-Life"]
    assert _offences("HALFLIFE writes you a read.") == ["HALFLIFE"]


def test_the_check_leaves_identifiers_and_the_physics_term_alone() -> None:
    assert _offences("Run `halflife init`, then call `halflife_help`.") == []
    assert _offences("Set `HALFLIFE_MODEL_ID` before running.") == []
    assert _offences("See https://github.com/Snorn/halflife for the source.") == []
    assert _offences("<a href='/halflife/docs'>the docs</a>") == []
    assert _offences("[the source](src/halflife/cli.py) explains it") == []
    assert _offences("Built in the open at github.com/Snorn/halflife.") == []
    assert _offences("<pre>$ halflife init</pre>") == []
    assert _offences("Every skill has a half-life, and HalfLife tops it up.") == []
