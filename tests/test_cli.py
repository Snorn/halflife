"""End-to-end through the CLI with generation stubbed out.

This is the wiring test: repositories, engine, session handling and rendering
all have to actually fit together. It does not touch the network.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from halflife import cli
from halflife.generation import engine
from tests.conftest import FakeClient, make_issue, make_plan

runner = CliRunner()


@pytest.fixture(autouse=True)
def wide_terminal(monkeypatch):
    """CliRunner reports an 80-column terminal, which wraps the `ls` table."""
    monkeypatch.setenv("COLUMNS", "200")


@pytest.fixture
def fake_generation(monkeypatch):
    """Make every GenerationClient the engine constructs return canned output."""
    client = FakeClient([make_plan(3), *[make_issue(n) for n in range(1, 6)]])
    monkeypatch.setattr(engine, "GenerationClient", lambda _settings: client)
    return client


def _run(*args) -> str:
    result = runner.invoke(cli.app, list(args))
    assert result.exit_code == 0, result.output + str(result.exception)
    return result.output


def test_subscribe_list_generate_read_feedback(migrated_db, fake_generation):
    output = _run("subscribe", "sap web dispatcher, 3, 5, 1d")
    assert "Subscribed" in output
    assert "Planned issue 1" in output  # the arc came back

    assert "sap web dispatcher" in _run("ls")

    # Generate the first issue for whatever is due.
    assert "Issue 1" in _run("run-due")
    assert "Issue 1" in _run("inbox")
    assert "Body of issue 1." in _run("read", "latest")

    # Reading marks it read, so the inbox empties.
    assert "Nothing unread" in _run("inbox")


def test_feedback_moves_the_subscriptions_depth(migrated_db, fake_generation):
    _run("subscribe", "postgres connection pooling, 3, 5, 1d")
    _run("run-due")

    inbox = _run("inbox")
    delivery_id = inbox.strip().split()[0]

    output = _run("feedback", delivery_id, "too-basic")
    assert "Depth 3 -> 4" in output

    assert " 4 " in _run("ls")


def test_feedback_at_the_ceiling_says_depth_is_unchanged(migrated_db, fake_generation):
    _run("subscribe", "tls certificate chains, 5, 5, 1d")
    _run("run-due")
    delivery_id = _run("inbox").strip().split()[0]

    assert "stays at 5" in _run("feedback", delivery_id, "too-basic")


def test_run_due_is_idempotent_within_the_interval(migrated_db, fake_generation):
    _run("subscribe", "kubernetes, 3, 5, 1d")
    assert "Issue 1" in _run("run-due")
    # The schedule advanced by a day, so a second run has nothing to do.
    assert "Nothing due" in _run("run-due")


def test_dry_run_does_not_generate(migrated_db, fake_generation):
    _run("subscribe", "kubernetes, 3, 5, 1d")
    calls_before = len(fake_generation.calls)

    output = _run("run-due", "--dry-run")

    assert "kubernetes" in output
    assert len(fake_generation.calls) == calls_before
    # Still due, because nothing was generated.
    assert "Issue 1" in _run("run-due")


def test_series_command_shows_plan_ledger_and_threads(migrated_db, fake_generation):
    _run("subscribe", "terraform state, 4, 5, 1d")
    _run("run-due")

    listing = _run("ls")
    sub_prefix = listing.strip().splitlines()[1].split()[0]

    output = _run("series", sub_prefix)
    assert "Plan" in output
    assert "Coverage ledger" in output
    assert "point-1a" in output
    assert "Open threads" in output


def test_pause_stops_a_subscription_coming_due(migrated_db, fake_generation):
    _run("subscribe", "kubernetes, 3, 5, 1d")
    sub_prefix = _run("ls").strip().splitlines()[1].split()[0]

    _run("pause", sub_prefix)
    assert "Nothing due" in _run("run-due")

    _run("resume", sub_prefix)
    assert "Issue 1" in _run("run-due")


def test_bad_shorthand_exits_nonzero_with_a_usable_message(migrated_db):
    result = runner.invoke(cli.app, ["subscribe", "x, 9, 5, 1d"])
    assert result.exit_code == 1
    assert "Depth must be between 1 and 5" in result.output


def test_subscription_survives_a_failed_plan(migrated_db, monkeypatch):
    """Planning needs an API key; the harness can do it instead.

    Regression: subscribe used to print "Subscribed", then abort on the planning
    failure and roll the whole transaction back, leaving the user with a success
    message and no subscription.
    """
    from halflife.generation.client import GenerationError

    class NoCredentials(FakeClient):
        def generate(self, **kwargs):
            raise GenerationError("No Anthropic credentials found.")

    monkeypatch.setattr(engine, "GenerationClient", lambda _s: NoCredentials([]))

    result = runner.invoke(cli.app, ["subscribe", "kubernetes, 3, 5, 1d"])

    assert result.exit_code == 0
    assert "Not planned" in result.output
    assert "ask your harness to plan" in result.output
    # The subscription is really there.
    assert "kubernetes" in _run("ls")


def test_no_plan_skips_the_arc_call(migrated_db, monkeypatch):
    client = FakeClient([])  # any call would raise
    monkeypatch.setattr(engine, "GenerationClient", lambda _settings: client)

    output = _run("subscribe", "kubernetes, 3, 5, 1d", "--no-plan")

    assert "Subscribed" in output
    assert client.calls == []


def test_flavour_switches_a_series(migrated_db, fake_generation):
    _run("subscribe", "sap web dispatcher, 4, 5, 1d")

    sub_id = _run("ls").strip().split("\n")[1].split()[0]
    output = _run("flavour", sub_id, "maintaining")

    assert "learning -> maintaining" in output
    assert " maintaining " in _run("ls")


def test_flavour_accepts_the_same_aliases_as_subscribe(migrated_db, fake_generation):
    """One alias map, so "m" cannot work in one place and not the other."""
    _run("subscribe", "terraform state, 3, 5, 1d")
    sub_id = _run("ls").strip().split("\n")[1].split()[0]

    assert "-> maintaining" in _run("flavour", sub_id, "m")
    assert "-> learning" in _run("flavour", sub_id, "learn")


def test_flavour_says_when_nothing_changed(migrated_db, fake_generation):
    _run("subscribe", "postgres connection pooling, 3, 5, 1d, learning")
    sub_id = _run("ls").strip().split("\n")[1].split()[0]

    assert "already learning" in _run("flavour", sub_id, "learning")


def test_flavour_rejects_an_unknown_value(migrated_db, fake_generation):
    _run("subscribe", "kubernetes, 3, 5, 1d")
    sub_id = _run("ls").strip().split("\n")[1].split()[0]

    result = runner.invoke(cli.app, ["flavour", sub_id, "nonsense"])

    assert result.exit_code != 0
    assert "learning" in result.output and "maintaining" in result.output


def test_flavour_leaves_depth_alone(migrated_db, fake_generation):
    """Pitch and stance are separate questions; the command answers one."""
    _run("subscribe", "tls certificate chains, 5, 5, 1d")
    sub_id = _run("ls").strip().split("\n")[1].split()[0]

    _run("flavour", sub_id, "maintaining")

    assert " 5 " in _run("ls")


def test_flavour_warns_that_the_plan_is_not_redrawn(migrated_db, fake_generation):
    """The arc was drawn under the old stance and is not rewritten, which the
    next issue would otherwise quietly contradict."""
    _run("subscribe", "linux cgroups v2, 3, 5, 1d")
    sub_id = _run("ls").strip().split("\n")[1].split()[0]

    assert "series plan stays as drawn" in _run("flavour", sub_id, "maintaining")


def _one_subscription(spec: str) -> str:
    _run("subscribe", spec)
    return _run("ls").strip().split("\n")[1].split()[0]


def test_duration_changes_the_word_budget(migrated_db, fake_generation):
    sub_id = _one_subscription("oauth device flow, 3, 5, 1d")

    output = _run("duration", sub_id, "10")

    assert "5 min -> 10 min" in output
    assert "2,000 words" in output


def test_duration_accepts_the_same_suffixes_as_subscribe(migrated_db, fake_generation):
    sub_id = _one_subscription("linux cgroups, 3, 5, 1d")

    assert "-> 12 min" in _run("duration", sub_id, "12m")


def test_duration_rejects_a_non_number(migrated_db, fake_generation):
    sub_id = _one_subscription("redis eviction, 3, 5, 1d")

    result = runner.invoke(cli.app, ["duration", sub_id, "nonsense"])

    assert result.exit_code != 0
    assert "number of minutes" in result.output


def test_frequency_changes_the_cadence(migrated_db, fake_generation):
    sub_id = _one_subscription("sap hana memory, 3, 5, 1d")

    output = _run("frequency", sub_id, "1w")

    assert "daily -> weekly" in output


def test_frequency_says_the_scheduled_issue_keeps_its_slot(migrated_db, fake_generation):
    """next_due_at was fixed when the last issue was recorded, so the change
    cannot move an issue that is already scheduled."""
    sub_id = _one_subscription("blameless incident review, 3, 5, 1d")

    output = _run("frequency", sub_id, "weekly")

    assert "already scheduled" in output
    assert "applies after that" in output


def test_frequency_rejects_an_unknown_cadence(migrated_db, fake_generation):
    sub_id = _one_subscription("tls chains, 3, 5, 1d")

    result = runner.invoke(cli.app, ["frequency", sub_id, "fortnightly"])

    assert result.exit_code != 0
    assert "hourly" in result.output and "weekly" in result.output


def test_a_change_that_changes_nothing_says_so(migrated_db, fake_generation):
    sub_id = _one_subscription("postgres pooling, 3, 5, 1d")

    assert "already 5 min" in _run("duration", sub_id, "5")
    assert "already daily" in _run("frequency", sub_id, "1d")


def test_changing_one_parameter_leaves_the_others_alone(migrated_db, fake_generation):
    """The three commands share a helper; the helper must not become a way to
    move something the caller did not name."""
    sub_id = _one_subscription("kubernetes admission, 4, 5, 1d, maintaining")

    _run("duration", sub_id, "15")

    listing = _run("ls")
    assert " 4 " in listing
    assert " daily " in listing
    assert " maintaining " in listing


def test_thread_tells_the_next_issue_what_was_missed(migrated_db, fake_generation):
    from halflife.db import session_scope
    from halflife.repository import series as series_repo
    from halflife.repository import subscriptions as subscription_repo

    _run("subscribe", "sap web dispatcher, 4, 5, 1d")
    sub_id = _run("ls").strip().split("\n")[1].split()[0]

    assert "Noted" in _run("thread", sub_id, "the semantic layer")

    with session_scope() as session:
        sub = subscription_repo.get_by_prefix(session, sub_id)
        threads = series_repo.get_for_subscription(session, sub.id).open_threads

    assert threads == [f"{series_repo.READER_THREAD_PREFIX} the semantic layer"]


def test_the_same_thread_twice_is_noted_once(migrated_db, fake_generation):
    _run("subscribe", "kubernetes, 3, 5, 1d")
    sub_id = _run("ls").strip().split("\n")[1].split()[0]

    _run("thread", sub_id, "admission webhook ordering")

    assert "Already noted" in _run("thread", sub_id, "admission webhook ordering")


def test_a_reader_thread_reaches_the_brief_marked_as_theirs(migrated_db, fake_generation):
    """The prefix is the whole mechanism: without it the generator cannot tell
    a reader's request from something a previous issue deferred."""
    from halflife.db import session_scope
    from halflife.generation import engine
    from halflife.repository import subscriptions as subscription_repo

    _run("subscribe", "postgres connection pooling, 3, 5, 1d")
    sub_id = _run("ls").strip().split("\n")[1].split()[0]
    _run("thread", sub_id, "connection pool sizing under pgbouncer")

    with session_scope() as session:
        sub = subscription_repo.get_by_prefix(session, sub_id)
        prompt = engine.build_brief(session=session, subscription=sub).user_prompt

    assert "Asked for by the reader: connection pool sizing under pgbouncer" in prompt
    assert "outrank the plan" in prompt


def test_threads_do_not_touch_depth(migrated_db, fake_generation):
    """This says what to write about, never at what level."""
    _run("subscribe", "tls certificate chains, 5, 5, 1d")
    sub_id = _run("ls").strip().split("\n")[1].split()[0]

    _run("thread", sub_id, "cross-signed chain expiry")

    assert " 5 " in _run("ls")


def test_thread_needs_a_series(migrated_db, fake_generation):
    result = runner.invoke(cli.app, ["thread", "zzzzzzzz", "anything"])

    assert result.exit_code != 0
    assert "No single subscription" in result.output
