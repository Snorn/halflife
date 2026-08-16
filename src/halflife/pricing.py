"""What generation actually cost.

Every ``Delivery`` records the tokens it used, so cost is computed from stored
data rather than tracked live — which means it works retrospectively and
survives restarts.

Two things this deliberately will not do: guess a price for a model it does not
know, and attribute a cost to an issue a harness generated. A harness issue
costs nothing *here* — whatever it cost was paid inside the tool the reader was
already running — and reporting a plausible number for it would misstate the
one figure this module exists to get right.
"""

from __future__ import annotations

from halflife.models.base import GenerationSource
from halflife.models.delivery import Delivery

# USD per million tokens, (input, output). Thinking bills as output, which at
# any effort above low is most of the bill. Update when pricing moves; an
# unrecognised model yields None rather than a wrong number.
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-fable-5": (10.00, 50.00),
}


def cost_usd(
    model_id: str | None, input_tokens: int | None, output_tokens: int | None
) -> float | None:
    """None when the model is unpriced or the token counts are unknown."""
    if not model_id or input_tokens is None or output_tokens is None:
        return None
    rates = PRICING.get(model_id)
    if rates is None:
        return None
    return input_tokens / 1e6 * rates[0] + output_tokens / 1e6 * rates[1]


def delivery_cost(delivery: Delivery) -> float | None:
    """What this issue cost in API spend. None if it cost none, or is unknown."""
    if delivery.source is GenerationSource.HARNESS:
        return None
    return cost_usd(delivery.model_id, delivery.input_tokens, delivery.output_tokens)


def describe(delivery: Delivery) -> str:
    """A short, honest phrase for one delivery's cost."""
    if delivery.source is GenerationSource.HARNESS:
        return "no API spend (written in-harness)"
    cost = delivery_cost(delivery)
    if cost is None:
        return "cost unknown"
    return f"${cost:.3f}"


def total(deliveries: list[Delivery]) -> tuple[float, int, int]:
    """Sum what is known, and count what is not.

    Returns (known cost, deliveries counted, deliveries with no known cost) so
    a caller can report coverage instead of implying the total is complete.
    """
    known = 0.0
    counted = 0
    unknown = 0
    for delivery in deliveries:
        cost = delivery_cost(delivery)
        if cost is None:
            unknown += 1
        else:
            known += cost
            counted += 1
    return known, counted, unknown
