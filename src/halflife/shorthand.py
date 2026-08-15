"""Power-user shorthand for creating subscriptions.

    sap web dispatcher, 3, 5, 1d
    kubernetes admission controllers, 4, 10, weekly, maintaining

Fields after the topic are optional and positional: depth, duration in minutes,
frequency, flavour. Frequency defaults to daily — hourly exists for cramming and
has to be asked for.
"""

from __future__ import annotations

from dataclasses import dataclass

from halflife.models.base import MAX_DEPTH, MIN_DEPTH, Flavour, Frequency

DEFAULT_DEPTH = 3
DEFAULT_DURATION_MINUTES = 5
DEFAULT_FREQUENCY = Frequency.DAILY
DEFAULT_FLAVOUR = Flavour.LEARNING

_FREQUENCY_ALIASES = {
    "1h": Frequency.HOURLY,
    "h": Frequency.HOURLY,
    "hourly": Frequency.HOURLY,
    "1d": Frequency.DAILY,
    "d": Frequency.DAILY,
    "daily": Frequency.DAILY,
    "1w": Frequency.WEEKLY,
    "w": Frequency.WEEKLY,
    "weekly": Frequency.WEEKLY,
}

_FLAVOUR_ALIASES = {
    "learning": Flavour.LEARNING,
    "learn": Flavour.LEARNING,
    "l": Flavour.LEARNING,
    "maintaining": Flavour.MAINTAINING,
    "maintain": Flavour.MAINTAINING,
    "m": Flavour.MAINTAINING,
}


class ShorthandError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedSubscription:
    topic: str
    depth: int
    duration_minutes: int
    frequency: Frequency
    flavour: Flavour


def parse_shorthand(raw: str) -> ParsedSubscription:
    parts = [p.strip() for p in raw.split(",")]
    if not parts or not parts[0]:
        raise ShorthandError("A topic is required.")
    if len(parts) > 5:
        raise ShorthandError(
            "Too many fields. Expected: topic, depth, duration, frequency, flavour."
        )

    topic = parts[0]
    depth = _parse_depth(parts[1]) if len(parts) > 1 and parts[1] else DEFAULT_DEPTH
    duration = _parse_duration(parts[2]) if len(parts) > 2 and parts[2] else DEFAULT_DURATION_MINUTES
    frequency = _parse_frequency(parts[3]) if len(parts) > 3 and parts[3] else DEFAULT_FREQUENCY
    flavour = _parse_flavour(parts[4]) if len(parts) > 4 and parts[4] else DEFAULT_FLAVOUR

    return ParsedSubscription(
        topic=topic,
        depth=depth,
        duration_minutes=duration,
        frequency=frequency,
        flavour=flavour,
    )


def _parse_depth(value: str) -> int:
    try:
        depth = int(value)
    except ValueError:
        raise ShorthandError(f"Depth must be a number {MIN_DEPTH}-{MAX_DEPTH}, got {value!r}.") from None
    if not MIN_DEPTH <= depth <= MAX_DEPTH:
        raise ShorthandError(f"Depth must be between {MIN_DEPTH} and {MAX_DEPTH}, got {depth}.")
    return depth


def _parse_duration(value: str) -> int:
    cleaned = value.removesuffix("min").removesuffix("m").strip()
    try:
        duration = int(cleaned)
    except ValueError:
        raise ShorthandError(f"Duration must be a number of minutes, got {value!r}.") from None
    if duration <= 0:
        raise ShorthandError("Duration must be greater than zero.")
    return duration


def _parse_frequency(value: str) -> Frequency:
    try:
        return _FREQUENCY_ALIASES[value.lower()]
    except KeyError:
        raise ShorthandError(
            f"Unknown frequency {value!r}. Use one of: hourly/1h, daily/1d, weekly/1w."
        ) from None


def _parse_flavour(value: str) -> Flavour:
    try:
        return _FLAVOUR_ALIASES[value.lower()]
    except KeyError:
        raise ShorthandError(
            f"Unknown flavour {value!r}. Use 'learning' or 'maintaining'."
        ) from None
