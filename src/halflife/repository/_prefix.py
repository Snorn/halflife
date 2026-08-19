"""Matching an id by its leading characters, safely.

The CLI and the MCP tools both accept the short id shown by `ls`, so a prefix
arrives from a command-line argument or a model-supplied tool parameter. Two
things follow, and both are the reason this is a shared helper rather than a
comprehension at each call site.

LIKE gives `%` and `_` their own meaning, so a prefix has to be escaped rather
than trusted to be a bare id — otherwise `%` matches every row and the caller
is handed somebody's record on a lookup that should have found nothing.

And the match belongs in SQL. Loading the table and filtering in Python read
the same to a caller and materialised every row in the process, including rows
belonging to other tenants that the caller had no business seeing.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement
from sqlalchemy.orm import InstrumentedAttribute

_ESCAPE = "\\"


def prefix_match(column: InstrumentedAttribute[str], prefix: str) -> ColumnElement[bool]:
    """A LIKE clause matching ``prefix`` as literal leading text."""
    escaped = (
        prefix.replace(_ESCAPE, _ESCAPE * 2)
        .replace("%", _ESCAPE + "%")
        .replace("_", _ESCAPE + "_")
    )
    return column.like(escaped + "%", escape=_ESCAPE)
