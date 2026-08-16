"""Unsubscribing.

Destructive and irreversible, so the tests care as much about what it refuses
to do without confirmation as about what it deletes.
"""

from __future__ import annotations

from sqlalchemy import select
from typer.testing import CliRunner

from halflife import cli
from halflife.generation import engine
from halflife.models.base import GenerationSource
from halflife.models.delivery import Delivery
from halflife.models.series import CoveragePoint, Series
from halflife.models.subscription import Subscription
from halflife.repository import subscriptions as subscription_repo
from halflife.shorthand import parse_shorthand
from tests.conftest import FakeClient, make_issue, make_plan

runner = CliRunner()


def _seeded(session, spec="sap web dispatcher, 4, 5, 1d"):
    """A subscription with a plan, an issue and a populated ledger."""
    sub = subscription_repo.create(session, parse_shorthand(spec))
    client = FakeClient([make_plan(3), make_issue(1)])
    engine.plan_series(session=session, subscription=sub, client=client)
    engine.generate_next(session=session, subscription=sub, client=client)
    session.flush()
    return sub


def test_summary_reports_what_would_be_lost(session):
    sub = _seeded(session)

    summary = subscription_repo.deletion_summary(session, sub)

    assert summary["issues"] == 1
    assert summary["coverage_points"] == 2


def test_delete_removes_the_series_ledger_and_deliveries(session):
    sub = _seeded(session)
    sub_id = sub.id

    subscription_repo.delete(session, sub)

    assert session.get(Subscription, sub_id) is None
    assert session.scalars(select(Series).where(Series.subscription_id == sub_id)).all() == []
    assert session.scalars(select(Delivery).where(Delivery.subscription_id == sub_id)).all() == []
    # Coverage points hang off the series and must go with it.
    assert session.scalars(select(CoveragePoint)).all() == []


def test_deleting_one_leaves_the_other_intact(session):
    keep = _seeded(session, "kubernetes, 3, 5, 1d")
    drop = _seeded(session, "postgres pooling, 3, 5, 1d")

    subscription_repo.delete(session, drop)

    assert session.get(Subscription, keep.id) is not None
    assert len(subscription_repo.list_all(session)) == 1
    assert session.scalars(select(Delivery)).all() != []


# ------------------------------------------------------------------ CLI


def _subscribe_via_cli(monkeypatch):
    client = FakeClient([make_plan(3), *[make_issue(n) for n in range(1, 4)]])
    monkeypatch.setattr(engine, "GenerationClient", lambda _s: client)
    assert runner.invoke(cli.app, ["subscribe", "sap web dispatcher, 4, 5, 1d"]).exit_code == 0
    assert runner.invoke(cli.app, ["run-due"]).exit_code == 0
    listing = runner.invoke(cli.app, ["ls"]).output
    return listing.strip().splitlines()[1].split()[0]


def test_cli_states_the_cost_and_aborts_on_no(migrated_db, monkeypatch):
    monkeypatch.setenv("COLUMNS", "200")
    prefix = _subscribe_via_cli(monkeypatch)

    result = runner.invoke(cli.app, ["unsubscribe", prefix], input="n\n")

    assert result.exit_code == 0
    assert "1 issue(s)" in result.output
    assert "cannot be undone" in result.output
    assert "Left alone" in result.output
    # Still there.
    assert "sap web dispatcher" in runner.invoke(cli.app, ["ls"]).output


def test_cli_deletes_on_yes(migrated_db, monkeypatch):
    monkeypatch.setenv("COLUMNS", "200")
    prefix = _subscribe_via_cli(monkeypatch)

    result = runner.invoke(cli.app, ["unsubscribe", prefix], input="y\n")

    assert result.exit_code == 0
    assert "Unsubscribed" in result.output
    assert "No subscriptions yet" in runner.invoke(cli.app, ["ls"]).output


def test_cli_yes_flag_skips_the_prompt(migrated_db, monkeypatch):
    monkeypatch.setenv("COLUMNS", "200")
    prefix = _subscribe_via_cli(monkeypatch)

    result = runner.invoke(cli.app, ["unsubscribe", prefix, "--yes"])

    assert result.exit_code == 0
    assert "Delete it?" not in result.output
    assert "Unsubscribed" in result.output


def test_cli_points_at_pause_as_the_safe_alternative(migrated_db, monkeypatch):
    monkeypatch.setenv("COLUMNS", "200")
    prefix = _subscribe_via_cli(monkeypatch)

    result = runner.invoke(cli.app, ["unsubscribe", prefix], input="n\n")

    assert "halflife pause" in result.output


def test_cli_unknown_prefix_exits_nonzero(migrated_db):
    result = runner.invoke(cli.app, ["unsubscribe", "zzzzzzzz", "--yes"])

    assert result.exit_code == 1
    assert "No single subscription matches" in result.output


def test_unsubscribe_is_not_exposed_over_mcp(migrated_db):
    """Deletion stays on the CLI: a model should not be able to call it."""
    import asyncio

    from halflife import mcp_server

    names = {t.name for t in asyncio.run(mcp_server.server.list_tools())}

    assert not any("unsubscribe" in n or "delete" in n for n in names)
