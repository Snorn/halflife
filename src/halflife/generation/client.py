"""Thin wrapper over the Anthropic API for structured generation.

Notes on the model surface (claude-opus-5), because they are easy to get wrong:

* Thinking is on by default. There is no token budget to set — reasoning depth
  is controlled by ``output_config.effort``.
* ``temperature`` / ``top_p`` / ``top_k`` are rejected. Steer with the prompt.
* Safety classifiers can decline a request with HTTP 200 and
  ``stop_reason == "refusal"``, so ``stop_reason`` is checked before the content
  is read. Server-side fallbacks are opted into by default so a decline is
  re-served rather than lost.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Generic, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from halflife.config import Settings
from halflife.generation.schemas import json_schema_for

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class GenerationError(RuntimeError):
    """Generation did not produce a usable result."""


@dataclass(frozen=True)
class GenerationResult(Generic[T]):
    parsed: T
    model_id: str
    effort: str
    input_tokens: int | None
    output_tokens: int | None


class GenerationClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        kwargs = {}
        if settings.anthropic_api_key:
            kwargs["api_key"] = settings.anthropic_api_key
        self._client = anthropic.Anthropic(**kwargs)
        self._use_fallbacks = True

    def generate(
        self,
        *,
        system: str,
        user: str,
        output_model: type[T],
    ) -> GenerationResult[T]:
        settings = self._settings
        params = {
            "model": settings.model_id,
            "max_tokens": settings.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {
                "effort": settings.effort,
                "format": {
                    "type": "json_schema",
                    "schema": json_schema_for(output_model),
                },
            },
        }

        response = self._call(params)

        if response.stop_reason == "refusal":
            detail = getattr(response, "stop_details", None)
            category = getattr(detail, "category", None)
            raise GenerationError(
                "The request was declined by safety classifiers"
                + (f" (category: {category})" if category else "")
                + ". Try rephrasing the topic."
            )
        if response.stop_reason == "max_tokens":
            raise GenerationError(
                "Output hit max_tokens before finishing. Raise HALFLIFE_MAX_TOKENS or lower "
                "the subscription's duration."
            )

        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise GenerationError(f"No text content in response (stop_reason={response.stop_reason}).")

        try:
            parsed = output_model.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise GenerationError(f"Response did not match the expected schema: {exc}") from exc

        usage = response.usage
        return GenerationResult(
            parsed=parsed,
            model_id=response.model,
            effort=settings.effort,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )

    def _call(self, params: dict):
        """Prefer the beta endpoint so refusals get re-served by a fallback model.

        The fallbacks parameter is a beta surface; if it is rejected, fall back
        to the plain endpoint for the rest of the process rather than failing
        the user's generation over it.
        """
        if self._use_fallbacks:
            try:
                return self._client.beta.messages.create(
                    **params, betas=[_FALLBACK_BETA], fallbacks="default"
                )
            except (anthropic.BadRequestError, TypeError) as exc:
                log.warning("Server-side fallbacks unavailable, continuing without them: %s", exc)
                self._use_fallbacks = False
        return self._client.messages.create(**params)
