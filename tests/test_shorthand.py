from __future__ import annotations

import pytest

from halflife.models.base import Flavour, Frequency
from halflife.shorthand import ShorthandError, parse_shorthand


def test_full_shorthand_from_the_design_doc():
    parsed = parse_shorthand("sap web dispatcher, 3, 5, 1d")
    assert parsed.topic == "sap web dispatcher"
    assert parsed.depth == 3
    assert parsed.duration_minutes == 5
    assert parsed.frequency is Frequency.DAILY
    assert parsed.flavour is Flavour.LEARNING


def test_topic_only_takes_defaults():
    parsed = parse_shorthand("kubernetes admission controllers")
    assert parsed.depth == 3
    assert parsed.duration_minutes == 5
    assert parsed.frequency is Frequency.DAILY


def test_frequency_defaults_to_daily_not_hourly():
    """Hourly exists for cramming and has to be asked for explicitly."""
    assert parse_shorthand("x").frequency is Frequency.DAILY
    assert parse_shorthand("x, 3, 5, hourly").frequency is Frequency.HOURLY


def test_maintaining_flavour():
    parsed = parse_shorthand("terraform state, 4, 10, weekly, maintaining")
    assert parsed.flavour is Flavour.MAINTAINING
    assert parsed.frequency is Frequency.WEEKLY
    assert parsed.depth == 4


def test_duration_suffixes_are_tolerated():
    assert parse_shorthand("x, 3, 10min").duration_minutes == 10
    assert parse_shorthand("x, 3, 10m").duration_minutes == 10


@pytest.mark.parametrize("spec", ["", "  ", ", 3, 5, 1d"])
def test_topic_is_required(spec):
    with pytest.raises(ShorthandError):
        parse_shorthand(spec)


@pytest.mark.parametrize("depth", ["0", "6", "-1", "three"])
def test_depth_is_bounded(depth):
    with pytest.raises(ShorthandError):
        parse_shorthand(f"x, {depth}, 5, 1d")


def test_unknown_frequency_is_rejected_with_the_options():
    with pytest.raises(ShorthandError, match="hourly"):
        parse_shorthand("x, 3, 5, fortnightly")


def test_too_many_fields():
    with pytest.raises(ShorthandError):
        parse_shorthand("a, 3, 5, 1d, learning, extra")
