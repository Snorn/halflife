"""Structured-output schemas for generation.

One API call per issue returns the body *and* the continuity bookkeeping, so the
coverage ledger stays in sync with what was actually written by construction
rather than by a second summarising call that can drift.

The Claude structured-outputs schema subset is narrower than full JSON Schema:
every object needs ``additionalProperties: false`` and a complete ``required``
list, and numeric/string constraints are not supported. Keep these models flat
and unconstrained; ``json_schema_for`` does the ``additionalProperties`` pass.
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
                node.setdefault("required", sorted(node["properties"]))
        for value in node.values():
            _harden(value)
    elif isinstance(node, list):
        for item in node:
            _harden(item)
