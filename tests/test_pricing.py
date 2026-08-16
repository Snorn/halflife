"""Cost reporting.

The one thing worse than no cost figure is a confident wrong one, so most of
these are about what it refuses to claim.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from halflife import cli, pricing
from halflife.generation import engine
from halflife.models.base import GenerationSource
from halflife.repository import subscriptions as subscription_repo
from halflife.shorthand import parse_shorthand
from tests.conftest import FakeClient, make_issue

runner = CliRunner()


def test_cost_is_input_plus_output_at_the_model_rate():
    # 1M in at $5 + 1M out at $25
    assert pricing.cost_usd("claude-opus-5", 1_000_000, 1_000_000) == pytest.approx(30.0)
    assert pricing.cost_usd("claude-opus-5", 2_000, 1_500) == pytest.approx(0.0475)


@pytest.mark.parametrize(
    ("model", "tokens_in", "tokens_out"),
    [
        ("claude-experimental-9", 100, 200),  # unpriced model
        (None, 100, 200),                     # model not reported
        ("claude-opus-5", None, 200),         # usage not reported
        ("claude-opus-5", 100, None),
    ],
)
def test_no_price_is_none_rather_than_a_guess(model, tokens_in, tokens_out):
    assert pricing.cost_usd(model, tokens_in, tokens_out) is None


def test_harness_issues_cost_nothing_here(session):
    """Whatever it cost was paid inside the reader's own tool."""
    sub = subscription_repo.create(session, parse_shorthand("kubernetes, 3, 5, 1d"))
    delivery = engine.record_issue(
        session=session,
        subscription=sub,
        issue=make_issue(1),
        source=GenerationSource.HARNESS,
        model_id="claude-opus-5",  # reported, but no tokens and not our spend
    )

    assert pricing.delivery_cost(delivery) is None
    assert "no API spend" in pricing.describe(delivery)


def test_api_issues_are_costed_from_recorded_tokens(session):
    sub = subscription_repo.create(session, parse_shorthand("kubernetes, 3, 5, 1d"))
    delivery = engine.generate_next(
        session=session, subscription=sub, client=FakeClient([make_issue(1)])
    )

    # FakeClient reports 1234 in / 567 out on claude-opus-5.
    assert pricing.delivery_cost(delivery) == pytest.approx(
        1234 / 1e6 * 5.0 + 567 / 1e6 * 25.0
    )
    assert pricing.describe(delivery).startswith("$")


def test_total_reports_what_it_could_not_price(session):
    sub = subscription_repo.create(session, parse_shorthand("kubernetes, 3, 5, 1d"))
    api = engine.generate_next(
        session=session, subscription=sub, client=FakeClient([make_issue(1)])
    )
    harness = engine.record_issue(
        session=session, subscription=sub, issue=make_issue(2), source=GenerationSource.HARNESS
    )

    known, priced, unknown = pricing.total([api, harness])

    assert priced == 1
    assert unknown == 1
    assert known == pytest.approx(pricing.delivery_cost(api))


# ---------------------------------------------------------------------- CLI


@pytest.fixture(autouse=True)
def wide_terminal(monkeypatch):
    monkeypatch.setenv("COLUMNS", "200")


def test_cost_command_with_nothing_yet(migrated_db):
    assert "No subscriptions yet" in runner.invoke(cli.app, ["cost"]).output


def test_cost_command_reports_spend_and_run_rate(migrated_db, monkeypatch):
    client = FakeClient([make_issue(1)])
    monkeypatch.setattr(engine, "GenerationClient", lambda _s: client)
    runner.invoke(cli.app, ["subscribe", "kubernetes, 3, 5, 1d", "--no-plan"])
    runner.invoke(cli.app, ["run-due"])

    output = runner.invoke(cli.app, ["cost"]).output

    assert "in API spend to date" in output
    assert "/month" in output
    assert "kubernetes" in output


def test_run_due_reports_what_it_just_spent(migrated_db, monkeypatch):
    client = FakeClient([make_issue(1)])
    monkeypatch.setattr(engine, "GenerationClient", lambda _s: client)
    runner.invoke(cli.app, ["subscribe", "kubernetes, 3, 5, 1d", "--no-plan"])

    output = runner.invoke(cli.app, ["run-due"]).output

    assert "$0.0" in output
    assert "Read with" in output


def test_run_rate_is_not_projected_without_a_measured_issue(migrated_db, monkeypatch):
    """A projection from zero data would be an invented number."""
    client = FakeClient([])
    monkeypatch.setattr(engine, "GenerationClient", lambda _s: client)
    runner.invoke(cli.app, ["subscribe", "kubernetes, 3, 5, 1d", "--no-plan"])

    output = runner.invoke(cli.app, ["cost"]).output

    assert "no run rate can be projected" in output
    assert "/month" not in output
