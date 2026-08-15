"""The structured-outputs schema subset is narrower than JSON Schema. If these
break, generation fails at the API with a 400 rather than in a useful place.
"""

from __future__ import annotations

from typing import Any

import pytest

from halflife.generation.schemas import GeneratedIssue, SeriesPlan, json_schema_for


def _objects(node: Any):
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            yield node
        for value in node.values():
            yield from _objects(value)
    elif isinstance(node, list):
        for item in node:
            yield from _objects(item)


@pytest.mark.parametrize("model", [GeneratedIssue, SeriesPlan])
def test_every_object_forbids_additional_properties(model):
    schema = json_schema_for(model)
    objects = list(_objects(schema))
    assert objects
    for obj in objects:
        assert obj["additionalProperties"] is False


@pytest.mark.parametrize("model", [GeneratedIssue, SeriesPlan])
def test_every_property_is_required(model):
    for obj in _objects(json_schema_for(model)):
        assert sorted(obj["required"]) == sorted(obj["properties"])


@pytest.mark.parametrize("model", [GeneratedIssue, SeriesPlan])
def test_no_unsupported_constraints(model):
    """minLength/maximum/multipleOf and friends are rejected by the API."""
    banned = {"minLength", "maxLength", "minimum", "maximum", "multipleOf", "pattern", "minItems", "maxItems"}
    stack = [json_schema_for(model)]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            assert not (banned & node.keys()), f"unsupported constraint in {node}"
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def test_nested_models_are_hardened_too():
    schema = json_schema_for(SeriesPlan)
    planned = schema["$defs"]["PlannedIssue"]
    assert planned["additionalProperties"] is False
    assert sorted(planned["required"]) == ["focus", "index", "title"]
