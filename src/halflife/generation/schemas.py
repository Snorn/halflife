"""Structured-output schemas for generation.

One API call per issue returns the body *and* the continuity bookkeeping, so the
coverage ledger stays in sync with what was actually written by construction
rather than by a second summarising call that can drift.

The Claude structured-outputs schema subset is narrower than full JSON Schema:
every object needs ``additionalProperties: false`` and a complete ``required``
list, and numeric/string constraints are not supported. Keep these models flat
and unconstrained; ``json_schema_for`` does the ``additionalProperties`` pass.

That subset is also why ``plan_index`` uses 0 rather than null for "no plan
entry": a nullable field means ``anyOf`` on the wire, which is outside the
subset this code has actually exercised. The column keeps that 0, and reserves
null for rows written before generation reported the field at all — the two are
different facts and collapsing them makes the legacy fallback fire on issues
that answered honestly.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GeneratedIssue(BaseModel):
    """One issue, plus the continuity state it produced."""

    title: str = Field(description="Title of this issue. Not repeated in the body.")
    body_markdown: str = Field(description="The issue itself, in Markdown, with no title heading.")
    covered_points_added: list[str] = Field(
        description=(
            "Short, atomic, self-contained claims that this issue established — one line each, "
            "phrased so a future issue can recognise the ground as covered."
        )
    )
    open_threads: list[str] = Field(
        description=(
            "Things this issue deliberately deferred, carried forward for a later issue to pick "
            "up or drop. Empty is fine and better than inventing."
        )
    )
    next_suggested: str = Field(
        description="One line: what the next issue should most usefully cover."
    )
    plan_index: int = Field(
        default=0,
        description=(
            "The number of the series-plan entry this issue covered. 0 if it took an open "
            "thread, or went somewhere the plan does not list. Do not guess a number to look "
            "compliant: 0 is the honest answer whenever the issue was not that entry."
        ),
    )


class CompactedLedger(BaseModel):
    claims: list[str] = Field(
        description=(
            "The merged claims replacing the entries given. Each specific enough that a future "
            "issue can recognise the ground as already covered."
        )
    )


class PlannedIssue(BaseModel):
    index: int
    title: str
    focus: str = Field(description="One sentence on what this issue establishes.")


class SeriesPlan(BaseModel):
    arc_summary: str = Field(description="Two sentences: where the series starts and ends up.")
    issues: list[PlannedIssue]


def json_schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic JSON schema, tightened to what structured outputs accepts."""
    schema = model.model_json_schema()
    _harden(schema)
    return schema


def _harden(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            node["additionalProperties"] = False
            if "properties" in node:
                # Every property, not just the ones Pydantic thinks are
                # required: a Python-side default is a convenience for local
                # callers and must not become an optional field on the wire,
                # which the structured-outputs subset does not allow.
                node["required"] = sorted(node["properties"])
        for value in node.values():
            _harden(value)
    elif isinstance(node, list):
        for item in node:
            _harden(item)
