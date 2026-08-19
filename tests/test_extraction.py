"""Extraction, and the boundary it exists to hold.

Most of these are not tests of behaviour but tests of *shape*: that there is
nowhere for content to go. A test asserting "we do not log conversations" would
be checking a habit; these check that the habit is not needed, because the
argument does not exist.

What is deliberately not tested here is whether the verbs are chosen well. That
would need a harness reading real conversations and a judge reading the
classifications beside them, and the second half is the content exposure the
whole design prevents. Treat classification quality as unknown.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from halflife.extraction import (
    ExtractedSignal,
    build_extraction_brief,
    record_signals,
)
from halflife.extraction.engine import hash_session
from halflife.models.base import Confidence, ContextCategory, SignalType, utcnow
from halflife.models.signal import Signal
from halflife.repository import signals as signal_repo

SESSION_KEY = "conversation-2026-08-19-morning"


def _signal(**overrides) -> ExtractedSignal:
    fields = {
        "topics": ["SAP Web Dispatcher"],
        "signal_type": SignalType.EXPLAINED_TO_AI,
        "confidence": Confidence.HIGH,
        "context_category": ContextCategory.TROUBLESHOOTING,
    }
    fields.update(overrides)
    return ExtractedSignal(**fields)


def _record(session, signals, session_key: str = SESSION_KEY):
    return record_signals(
        session=session,
        signals=signals,
        session_key=session_key,
        harness="claude-code",
        agent_version="test",
    )


# ------------------------------------------------------------ the boundary


def test_a_signal_has_nowhere_to_put_content():
    """The strongest form this guarantee takes: not a rule about what callers
    should send, but the absence of a field to send it in."""
    fields = set(ExtractedSignal.model_fields)

    assert fields == {"topics", "signal_type", "confidence", "context_category"}


def test_recording_takes_no_conversation_argument():
    """record_signals cannot be handed a transcript, an excerpt or a summary,
    because no parameter would accept one."""
    import inspect

    parameters = set(inspect.signature(record_signals).parameters)

    assert parameters == {
        "session",
        "signals",
        "session_key",
        "harness",
        "agent_version",
        "tenant_id",
        "user_id",
    }


def test_evidence_is_null_on_every_stored_row(session):
    rows = _record(session, [_signal(), _signal(signal_type=SignalType.STRUGGLED)])

    assert rows
    assert all(row.evidence is None for row in rows)


def test_storing_evidence_is_refused(session):
    """v1 keeps evidence permanently null. A future change that starts filling
    it should fail here rather than ship."""
    row = Signal(
        id="x",
        tenant_id="t",
        user_id="u",
        schema_version="1",
        occurred_at=utcnow(),
        session_id=hash_session(SESSION_KEY),
        topics=["x"],
        signal_type=SignalType.APPLIED,
        confidence=Confidence.LOW,
        context_category=ContextCategory.CODING,
        evidence="they said the dispatcher was misconfigured",
        harness="h",
        agent_version="v",
        extraction_prompt_version="1",
    )

    with pytest.raises(signal_repo.PrivacyViolation, match="permanently null"):
        signal_repo.assert_no_content(row)


def test_the_session_key_is_stored_only_as_a_digest(session):
    rows = _record(session, [_signal()])

    assert rows[0].session_id == hash_session(SESSION_KEY)
    assert SESSION_KEY not in rows[0].session_id
    assert len(rows[0].session_id) == 64


def test_one_sitting_shares_a_session_id_and_two_do_not(session):
    """Why the digest exists: relating signals from one sitting without any
    route back to the sitting."""
    first = _record(session, [_signal()])
    same = _record(session, [_signal(signal_type=SignalType.APPLIED)])
    other = _record(session, [_signal()], session_key="a-different-conversation")

    assert first[0].session_id == same[0].session_id
    assert first[0].session_id != other[0].session_id


def test_there_is_no_read_path_for_individual_signals():
    """CLAUDE.md's aggregation rule, enforced by what the repository lacks."""
    exposed = {name for name in vars(signal_repo) if not name.startswith("_")}

    assert "get" not in exposed
    assert "get_by_prefix" not in exposed
    assert "list_all" not in exposed


# --------------------------------------------------------------- the brief


def test_the_brief_carries_the_vocabularies_but_not_a_taxonomy():
    """Topics are free text at the edge and normalised centrally: shipping a
    topic list would have the model answer from the list."""
    brief = build_extraction_brief()

    assert brief.signal_types == [member.value for member in SignalType]
    assert brief.confidence_levels == ["low", "medium", "high"]
    assert len(brief.context_categories) == 5
    assert "topics" not in {field for field in vars(brief) if field.endswith("_list")}


def test_the_brief_needs_no_session_passed_to_it():
    import inspect

    assert not inspect.signature(build_extraction_brief).parameters


def test_the_prompt_forbids_quoting_the_session():
    """Whitespace is normalised first: the prompt is wrapped prose, and
    re-wrapping a paragraph must not read as deleting the rule in it."""
    prompt = " ".join(build_extraction_brief().system_prompt.split())

    for instruction in [
        "No quotations.",
        "No sentences from the session.",
        "No file paths, code, identifiers, error messages",
        "no field for context and no field for evidence",
        "a tool that never receives content cannot leak it",
    ]:
        assert instruction in prompt, f"the prompt no longer says: {instruction}"


# -------------------------------------------------------------- recording


def test_signals_without_a_topic_are_dropped(session):
    """A verb with no subject cannot be aggregated and is not worth storing."""
    rows = _record(session, [_signal(topics=[]), _signal(topics=["  "]), _signal()])

    assert len(rows) == 1


def test_provenance_is_recorded_for_every_signal(session):
    """A prompt version that starts mis-classifying has to be identifiable, so
    its rows can be excluded rather than guessed at."""
    row = _record(session, [_signal()])[0]

    assert row.extraction_prompt_version == build_extraction_brief().prompt_version
    assert row.harness == "claude-code"
    assert row.schema_version == "1"


def test_the_only_read_is_a_count_over_a_window(session):
    _record(session, [_signal(), _signal(signal_type=SignalType.STRUGGLED)])

    recent = signal_repo.count_in_window(session, since=utcnow() - timedelta(hours=1))
    ancient = signal_repo.count_in_window(session, since=utcnow() + timedelta(hours=1))

    assert recent == 2
    assert ancient == 0


def test_topics_survive_as_written_at_the_edge(session):
    """Normalisation happens centrally, later. The agent's wording is kept."""
    row = _record(session, [_signal(topics=[" SAP Web Dispatcher ", "TLS"])])[0]

    assert row.topics == ["SAP Web Dispatcher", "TLS"]


def test_the_mcp_tool_reports_no_read_path(session, monkeypatch):
    from halflife import mcp_server

    class _Scope:
        def __enter__(self):
            return session

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(mcp_server, "session_scope", _Scope)

    result = json.loads(
        mcp_server.halflife_record_signals(
            signals=[_signal()],
            session_key=SESSION_KEY,
            harness="claude-code",
        )
    )

    assert result["recorded"] == 1
    assert "write-only" in result["note"]
