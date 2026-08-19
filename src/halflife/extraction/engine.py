"""The extraction seam: hand out a prompt, take back classifications.

The same shape as generation's ``build_brief`` / ``record_issue``, and for a
sharper reason. Generation splits this way so that two backends can share one
set of prompts. Extraction splits this way so that conversation text never
becomes an argument to anything here: the harness reads the session it is
already in, and what crosses back is verbs.

Nothing in this module accepts content, and there is no parameter it could be
smuggled through. That is the design, not a convention to be careful about.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from halflife import LOCAL_TENANT_ID, LOCAL_USER_ID
from halflife.extraction import prompts
from halflife.models.base import (
    SIGNAL_SCHEMA_VERSION,
    Confidence,
    ContextCategory,
    SignalType,
    new_id,
    utcnow,
)
from halflife.models.signal import Signal
from halflife.repository import signals as signal_repo


class ExtractedSignal(BaseModel):
    """One classification, as it arrives from the harness.

    Every field is drawn from a fixed vocabulary except ``topics``, which is
    free text by design — the taxonomy is normalised centrally rather than
    shipped to the agent. There is no field for evidence, context or excerpts,
    which is what makes the boundary structural rather than procedural.
    """

    topics: list[str] = Field(
        description="Subjects involved, as short noun phrases. Names, not descriptions."
    )
    signal_type: SignalType = Field(description="One of the seven behavioural verbs.")
    confidence: Confidence = Field(
        description="The agent's confidence in this classification: low, medium or high."
    )
    context_category: ContextCategory = Field(
        description="coding, troubleshooting, research, writing or meeting-prep."
    )


@dataclass(frozen=True)
class ExtractionBrief:
    system_prompt: str
    user_prompt: str
    prompt_version: str
    signal_types: list[str]
    confidence_levels: list[str]
    context_categories: list[str]


def build_extraction_brief() -> ExtractionBrief:
    """Everything the harness needs to classify a session it is already in.

    Takes no arguments on purpose: there is no session to pass in, because the
    conversation stays where it is.
    """
    return ExtractionBrief(
        system_prompt=prompts.build_system_prompt(),
        user_prompt=prompts.build_user_prompt(),
        prompt_version=prompts.EXTRACTION_PROMPT_VERSION,
        signal_types=[member.value for member in SignalType],
        confidence_levels=[member.value for member in Confidence],
        context_categories=[member.value for member in ContextCategory],
    )


def hash_session(session_key: str) -> str:
    """Reduce whatever the harness calls this session to a digest.

    The point of a session id is to let two signals from one sitting be seen as
    related. Nothing needs the original to do that, so nothing keeps it: the
    digest is computed here, the argument goes out of scope, and no caller
    stores or logs what came in.
    """
    return hashlib.sha256(session_key.encode("utf-8")).hexdigest()


def record_signals(
    *,
    session: Session,
    signals: list[ExtractedSignal],
    session_key: str,
    harness: str,
    agent_version: str,
    tenant_id: str = LOCAL_TENANT_ID,
    user_id: str = LOCAL_USER_ID,
) -> list[Signal]:
    """Persist classifications. Write-only: nothing reads these back per-row."""
    session_id = hash_session(session_key)
    now = utcnow()

    rows = [
        Signal(
            id=new_id(),
            tenant_id=tenant_id,
            user_id=user_id,
            schema_version=SIGNAL_SCHEMA_VERSION,
            occurred_at=now,
            session_id=session_id,
            topics=[topic.strip() for topic in signal.topics if topic.strip()],
            signal_type=signal.signal_type,
            confidence=signal.confidence,
            context_category=signal.context_category,
            # Never set from input; there is no input that could set it.
            evidence=None,
            harness=harness,
            agent_version=agent_version,
            extraction_prompt_version=prompts.EXTRACTION_PROMPT_VERSION,
        )
        for signal in signals
        if any(topic.strip() for topic in signal.topics)
    ]

    for row in rows:
        signal_repo.assert_no_content(row)
        session.add(row)
    session.flush()
    return rows
