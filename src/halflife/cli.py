"""The step-1 surface: one person, one machine, reading their own subscriptions.

Everything here goes through repositories and the engine, so that the MCP server
(step 2) and the API (step 3) are new front doors on the same code.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from halflife import guide, pricing
from halflife.config import get_settings
from halflife.db import session_scope
from halflife.generation import GenerationError, engine
from halflife.migrations_runner import upgrade_to_head
from halflife.models.base import (
    issue_cap,
    CoverageKind,
    Feedback,
    Frequency,
    GenerationSource,
    SubscriptionStatus,
    utcnow,
)
from halflife.models.delivery import Delivery
from halflife.repository import deliveries as delivery_repo
from halflife.repository import series as series_repo
from halflife.repository import subscriptions as subscription_repo
from halflife.shorthand import (
    ShorthandError,
    parse_duration,
    parse_flavour,
    parse_frequency,
    parse_shorthand,
)

app = typer.Typer(add_completion=False, help="HalfLife — keep your skills from decaying.")
console = Console()

_FEEDBACK_ALIASES = {
    "too-basic": Feedback.TOO_BASIC,
    "too_basic": Feedback.TOO_BASIC,
    "basic": Feedback.TOO_BASIC,
    "just-right": Feedback.JUST_RIGHT,
    "just_right": Feedback.JUST_RIGHT,
    "ok": Feedback.JUST_RIGHT,
    "too-advanced": Feedback.TOO_ADVANCED,
    "too_advanced": Feedback.TOO_ADVANCED,
    "advanced": Feedback.TOO_ADVANCED,
    "already-knew": Feedback.ALREADY_KNEW,
    "already_knew": Feedback.ALREADY_KNEW,
    "knew": Feedback.ALREADY_KNEW,
    "wrong-subject": Feedback.WRONG_SUBJECT,
    "wrong_subject": Feedback.WRONG_SUBJECT,
    "wrong": Feedback.WRONG_SUBJECT,
}


def _issues_cell(sub, series) -> str:
    """Issue count, against the cap where the depth has one."""
    written = series.issue_count if series else 0
    cap = issue_cap(sub.depth)
    return f"{written}/{cap}" if cap else str(written)


def _state_cell(sub) -> str:
    if sub.status is not SubscriptionStatus.ACTIVE:
        return "[dim]paused[/dim]"
    if subscription_repo.is_complete(sub):
        return "[dim]complete[/dim]"
    return ""


def _short(identifier: str) -> str:
    return identifier[:8]


def _fail(message: str) -> None:
    console.print(f"[red]{message}[/red]")
    raise typer.Exit(code=1)


@app.command("help")
def show_guide() -> None:
    """How HalfLife works: the loop, what to ask your harness, and every command."""
    console.print(Markdown(guide.guide_text()))


@app.command()
def init() -> None:
    """Create or upgrade the local database."""
    upgrade_to_head()
    console.print("[green]Database is up to date.[/green]")


@app.command()
def subscribe(
    spec: str = typer.Argument(..., help='e.g. "sap web dispatcher, 3, 5, 1d"'),
    plan: bool = typer.Option(True, "--plan/--no-plan", help="Sketch the series arc up front."),
) -> None:
    """Create a subscription. Shorthand: topic, depth, duration, frequency, flavour."""
    try:
        parsed = parse_shorthand(spec)
    except ShorthandError as exc:
        _fail(str(exc))
        return

    with session_scope() as session:
        subscription = subscription_repo.create(session, parsed)
        console.print(
            f"[green]Subscribed[/green] {_short(subscription.id)}  {parsed.topic}  "
            f"depth {parsed.depth}  {parsed.duration_minutes}min  "
            f"{parsed.frequency.value}  {parsed.flavour.value}"
        )
        planned = None
        if plan:
            with console.status("Planning the series arc..."):
                try:
                    planned = engine.plan_series(session=session, subscription=subscription)
                except GenerationError as exc:
                    # Planning is optional and needs an API key; the harness can
                    # do it instead. Failing the whole subscribe here would throw
                    # away a subscription that is otherwise perfectly usable.
                    console.print(f"\n[yellow]Not planned:[/yellow] {exc}")

        if planned is not None:
            console.print(f"\n[dim]{planned.arc_summary}[/dim]\n")
            for entry in planned.plan:
                console.print(f"  {entry['index']:>2}. {entry['title']}")
            console.print(
                "\n[dim]Next: ask your harness for the first issue, or[/dim] halflife run-due"
            )
        else:
            console.print(
                "\n[dim]Next: ask your harness to plan this series and write the first "
                "issue.[/dim]"
            )


@app.command("ls")
def list_subscriptions() -> None:
    """List subscriptions."""
    with session_scope() as session:
        subscriptions = subscription_repo.list_all(session)
        if not subscriptions:
            console.print("[dim]No subscriptions yet. Try: halflife subscribe \"kubernetes, 3, 5, 1d\"[/dim]")
            return

        table = Table(box=None, pad_edge=False)
        for column in ("id", "topic", "depth", "mins", "freq", "flavour", "issues", "next due", ""):
            table.add_column(column)
        for sub in subscriptions:
            series = sub.series
            table.add_row(
                _short(sub.id),
                sub.topic,
                str(sub.depth),
                str(sub.duration_minutes),
                sub.frequency.value,
                sub.flavour.value,
                _issues_cell(sub, series),
                sub.next_due_at.strftime("%Y-%m-%d %H:%M"),
                _state_cell(sub),
            )
        console.print(table)


@app.command("run-due")
def run_due(
    limit: int = typer.Option(0, help="Stop after this many issues. 0 means no limit."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what is due without generating."),
) -> None:
    """Generate an issue for every subscription that is due."""
    with session_scope() as session:
        due = subscription_repo.list_due(session, now=utcnow())
        if not due:
            console.print("[dim]Nothing due.[/dim]")
            return
        if limit:
            due = due[:limit]

        if dry_run:
            for sub in due:
                console.print(f"  {_short(sub.id)}  {sub.topic}  (due {sub.next_due_at:%Y-%m-%d %H:%M})")
            return

        generated = 0
        produced: list[Delivery] = []
        for sub in due:
            with console.status(f"Generating: {sub.topic}"):
                try:
                    delivery = engine.generate_next(session=session, subscription=sub)
                except GenerationError as exc:
                    console.print(f"[red]{sub.topic}: {exc}[/red]")
                    continue
            generated += 1
            produced.append(delivery)
            console.print(
                f"[green]#{delivery.issue_number}[/green] {delivery.title}  "
                f"[dim]{_short(delivery.id)} · {pricing.describe(delivery)}[/dim]"
            )

        # Generating and reading are separate steps, which is not obvious from
        # a line of output that looks like it might have been the whole thing.
        if generated:
            spend = pricing.total(produced)[0]
            console.print(
                f"\n[dim]{generated} waiting, ${spend:.3f}. Read with:[/dim] "
                "halflife read latest"
            )


@app.command()
def generate(
    subscription: str = typer.Argument(..., help="Subscription id or prefix."),
) -> None:
    """Generate the next issue now, regardless of schedule."""
    with session_scope() as session:
        sub = subscription_repo.get_by_prefix(session, subscription)
        if sub is None:
            _fail(f"No single subscription matches {subscription!r}.")
            return
        with console.status(f"Generating: {sub.topic}"):
            try:
                delivery = engine.generate_next(session=session, subscription=sub)
            except GenerationError as exc:
                _fail(str(exc))
                return
        _render(delivery)
        delivery_repo.mark_read(session, delivery)


@app.command()
def inbox() -> None:
    """Show unread issues."""
    with session_scope() as session:
        unread = delivery_repo.list_unread(session)
        if not unread:
            console.print("[dim]Nothing unread.[/dim]")
            return
        for delivery in unread:
            console.print(
                f"  {_short(delivery.id)}  [bold]{delivery.title}[/bold]  "
                f"[dim]{delivery.subscription.topic} · depth {delivery.depth} · "
                f"#{delivery.issue_number}[/dim]"
            )


@app.command()
def read(
    delivery: str = typer.Argument("latest", help="Delivery id/prefix, or 'latest'."),
) -> None:
    """Read an issue."""
    with session_scope() as session:
        if delivery == "latest":
            unread = delivery_repo.list_unread(session)
            recent = delivery_repo.list_recent(session, limit=1)
            target = unread[0] if unread else (recent[0] if recent else None)
        else:
            target = delivery_repo.get_by_prefix(session, delivery)
        if target is None:
            _fail(f"No single delivery matches {delivery!r}.")
            return
        _render(target)
        delivery_repo.mark_read(session, target)


@app.command()
def feedback(
    delivery: str = typer.Argument(..., help="Delivery id or prefix."),
    verdict: str = typer.Argument(
        ...,
        help="too-basic | just-right | too-advanced | already-knew | wrong-subject",
    ),
) -> None:
    """Record feedback on an issue.

    Two axes. too-basic and too-advanced are about the *level*, and nudge the
    subscription's depth. already-knew and wrong-subject are about the
    *subject* — the pitch was right, the ground was wrong — and leave depth
    alone; the next few issues are told to go elsewhere instead.
    """
    parsed = _FEEDBACK_ALIASES.get(verdict.lower())
    if parsed is None:
        _fail(
            "Verdict must be one of: too-basic, just-right, too-advanced, "
            "already-knew, wrong-subject."
        )
        return

    with session_scope() as session:
        target = delivery_repo.get_by_prefix(session, delivery)
        if target is None:
            _fail(f"No single delivery matches {delivery!r}.")
            return
        delivery_repo.set_feedback(session, target, parsed)
        subscription = target.subscription
        before = subscription.depth
        after = subscription_repo.apply_feedback_to_depth(session, subscription, parsed)
        if not parsed.is_about_depth:
            console.print(
                f"[green]Noted.[/green] Depth stays at {after}; the next issues will "
                "be told to take different ground."
            )
        elif after == before:
            console.print(f"[green]Noted.[/green] Depth stays at {after}.")
        else:
            console.print(f"[green]Noted.[/green] Depth {before} -> {after} for future issues.")


def _change(prefix: str, describe, note=None, **updates) -> None:
    """Apply one parameter change to a subscription and report what moved.

    Shared by the three change commands because the interesting part of each is
    the one line that parses its own value; everything around it — resolving a
    prefix, noticing that nothing changed, saying when it takes effect — is the
    same question every time and only stays consistent if it is answered once.
    """
    with session_scope() as session:
        sub = subscription_repo.get_by_prefix(session, prefix)
        if sub is None:
            _fail(f"No single subscription matches {prefix!r}.")
            return

        before = describe(sub)
        subscription_repo.update_parameters(session, sub, **updates)
        after = describe(sub)

        if before == after:
            console.print(f"[green]Unchanged.[/green] {sub.topic} is already {after}.")
            return

        console.print(f"[green]{sub.topic}[/green]: {before} -> {after}, from the next issue.")
        if note is not None:
            line = note(sub)
            if line:
                console.print(f"  {line}")


@app.command()
def flavour(
    subscription: str = typer.Argument(..., help="Subscription id or prefix."),
    value: str = typer.Argument(..., help="learning or maintaining"),
) -> None:
    """Switch a series between learning and maintaining.

    `learning` assumes you are building the skill up and wants ground gained
    each issue. `maintaining` assumes you were good at this once: it leads with
    what decays first — exact syntax, thresholds and defaults, the ordering of
    steps, what has changed since you last used it — and does not re-motivate
    the topic.

    Depth is unaffected. This is a different question from how deep to pitch,
    and answering one does not answer the other.
    """
    try:
        parsed = parse_flavour(value)
    except ShorthandError as exc:
        _fail(str(exc))
        return

    _change(
        subscription,
        lambda sub: sub.flavour.value,
        # The arc was drawn under the old stance and is not redrawn here.
        note=lambda sub: (
            "The series plan stays as drawn; the change is in how each issue is written."
            if sub.series is not None and sub.series.plan
            else ""
        ),
        flavour=parsed,
    )


@app.command()
def duration(
    subscription: str = typer.Argument(..., help="Subscription id or prefix."),
    minutes: str = typer.Argument(..., help="Minutes per issue, e.g. 5 or 10m"),
) -> None:
    """Change how long an issue should take to read.

    Length is the only thing this moves. Depth sets what you are assumed to
    already know, so a longer issue at the same depth covers more ground rather
    than explaining the same ground more slowly.
    """
    try:
        parsed = parse_duration(minutes)
    except ShorthandError as exc:
        _fail(str(exc))
        return

    settings = get_settings()
    _change(
        subscription,
        lambda sub: f"{sub.duration_minutes} min",
        note=lambda sub: (
            f"Issues will run to about {sub.duration_minutes * settings.words_per_minute:,} words."
        ),
        duration_minutes=parsed,
    )


@app.command()
def frequency(
    subscription: str = typer.Argument(..., help="Subscription id or prefix."),
    value: str = typer.Argument(..., help="hourly/1h, daily/1d or weekly/1w"),
) -> None:
    """Change how often an issue is due.

    Daily is the default. Weekly suits a maintaining series; hourly exists for
    cramming and has to be asked for.
    """
    try:
        parsed = parse_frequency(value)
    except ShorthandError as exc:
        _fail(str(exc))
        return

    _change(
        subscription,
        lambda sub: sub.frequency.value,
        # next_due_at was fixed when the last issue was recorded, using the
        # interval in force then. Saying so beats a user waiting a week for an
        # issue that was always going to arrive tomorrow.
        note=lambda sub: (
            f"The next issue is already scheduled for {sub.next_due_at:%Y-%m-%d %H:%M}; "
            "the new interval applies after that."
            if sub.next_due_at is not None
            else ""
        ),
        frequency=parsed,
    )


@app.command()
def thread(
    subscription: str = typer.Argument(..., help="Subscription id or prefix."),
    text: str = typer.Argument(..., help="What the series should cover."),
) -> None:
    """Tell a series it missed something.

    The next issue is shown this and told it outranks the plan. It is advisory,
    not a queue: a generator that takes the subject clears it, and one that
    judges it not worth an issue drops it. Nothing here guarantees coverage.

    Depth is untouched. This says what to write about, never at what level.
    """
    with session_scope() as session:
        sub = subscription_repo.get_by_prefix(session, subscription)
        if sub is None:
            _fail(f"No single subscription matches {subscription!r}.")
            return

        state = series_repo.get_for_subscription(session, sub.id)
        if state is None:
            _fail("That subscription has no series yet; write an issue first.")
            return

        before = len(state.open_threads)
        threads = series_repo.add_thread(session, state, text)
        if len(threads) == before:
            console.print("[green]Already noted.[/green] That thread is on the series.")
            return

        console.print(f"[green]Noted for {sub.topic}.[/green] The next issue is told about it.")


@app.command()
def series(
    subscription: str = typer.Argument(..., help="Subscription id or prefix."),
    full: bool = typer.Option(False, "--full", help="Include entries folded into summaries."),
) -> None:
    """Inspect series continuity state: the plan, the coverage ledger, open threads."""
    with session_scope() as session:
        sub = subscription_repo.get_by_prefix(session, subscription)
        if sub is None:
            _fail(f"No single subscription matches {subscription!r}.")
            return
        state = series_repo.get_for_subscription(session, sub.id)
        if state is None:
            _fail("That subscription has no series.")
            return

        console.print(f"[bold]{sub.topic}[/bold]  depth {sub.depth}  {state.issue_count} issues written\n")
        if state.arc_summary:
            console.print(f"[dim]{state.arc_summary}[/dim]\n")

        console.print("[bold]Plan[/bold]")
        for entry in state.plan:
            written = entry["index"] <= state.issue_count
            marker = "[green]x[/green]" if written else " "
            console.print(f"  [{marker}] {entry['index']:>2}. {entry['title']} — [dim]{entry['focus']}[/dim]")

        points = series_repo.coverage_points(session, state.id)
        active = [p for p in points if p.compacted_at is None]
        folded = len(points) - len(active)
        header = f"\n[bold]Coverage ledger[/bold] ({len(active)} active"
        if folded:
            header += f", {folded} folded into summaries"
        console.print(header + ")")
        for point in points if full else active:
            if point.compacted_at is not None:
                console.print(f"  [dim]x {point.point}[/dim]")
                continue
            marker = "[cyan]~[/cyan]" if point.kind is CoverageKind.SUMMARY else "-"
            console.print(f"  {marker} {point.point}")
        if folded and not full:
            console.print(
                f"\n  [dim]~ marks a summary. Folded entries are kept, not deleted —[/dim] "
                f"halflife series {_short(sub.id)} --full"
            )

        console.print("\n[bold]Open threads[/bold]")
        if state.open_threads:
            for thread in state.open_threads:
                console.print(f"  - {thread}")
        else:
            console.print("  [dim]none[/dim]")


_ISSUES_PER_MONTH = {Frequency.HOURLY: 730.0, Frequency.DAILY: 30.4, Frequency.WEEKLY: 4.3}


@app.command()
def cost() -> None:
    """What generation has cost so far, and what the current subscriptions run to."""
    with session_scope() as session:
        subscriptions = subscription_repo.list_all(session)
        if not subscriptions:
            console.print("[dim]No subscriptions yet.[/dim]")
            return

        table = Table(box=None, pad_edge=False)
        for column in ("topic", "issues", "api", "in-harness", "spent", "per issue"):
            table.add_column(column)

        grand_known = 0.0
        grand_priced = 0
        grand_unknown = 0

        for sub in subscriptions:
            deliveries = delivery_repo.list_for_subscription(session, sub.id)
            known, priced, unknown = pricing.total(deliveries)
            in_harness = sum(
                1 for d in deliveries if d.source is GenerationSource.HARNESS
            )
            grand_known += known
            grand_priced += priced
            grand_unknown += unknown
            table.add_row(
                sub.topic,
                str(len(deliveries)),
                str(len(deliveries) - in_harness),
                str(in_harness),
                f"${known:.2f}",
                f"${known / priced:.3f}" if priced else "—",
            )
        console.print(table)

        console.print(f"\n[bold]${grand_known:.2f}[/bold] in API spend to date")
        if grand_unknown:
            console.print(
                f"  [dim]{grand_unknown} issue(s) excluded: written in-harness, or "
                f"on a model with no price on file.[/dim]"
            )

        if not grand_priced:
            console.print(
                "  [dim]No priced issues yet, so no run rate can be projected.[/dim]"
            )
            return

        # Projected from this installation's own measured average, not from a
        # figure baked in here — effort and topic both move it.
        per_issue = grand_known / grand_priced
        monthly = sum(
            _ISSUES_PER_MONTH[s.frequency] * per_issue
            for s in subscriptions
            if s.status is SubscriptionStatus.ACTIVE
        )
        console.print(
            f"  [dim]At ${per_issue:.3f}/issue measured here, the active "
            f"subscriptions run to about ${monthly:.2f}/month if every issue is "
            f"generated via the API.[/dim]"
        )


@app.command()
def unsubscribe(
    subscription: str = typer.Argument(..., help="Subscription id or prefix."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt."),
) -> None:
    """Delete a subscription, its series and every issue it has delivered.

    Irreversible. Use `pause` instead to stop delivery while keeping the series.
    """
    with session_scope() as session:
        sub = subscription_repo.get_by_prefix(session, subscription)
        if sub is None:
            _fail(f"No single subscription matches {subscription!r}.")
            return

        summary = subscription_repo.deletion_summary(session, sub)
        console.print(
            f"[bold]{sub.topic}[/bold]  depth {sub.depth}  {sub.frequency.value}\n"
            f"  {summary['issues']} issue(s) and {summary['coverage_points']} coverage "
            f"point(s) will be deleted."
        )

        if not yes:
            console.print(
                "[dim]This cannot be undone. `halflife pause` stops delivery "
                "without deleting anything.[/dim]"
            )
            if not typer.confirm("Delete it?"):
                console.print("[dim]Left alone.[/dim]")
                return

        topic = sub.topic
        subscription_repo.delete(session, sub)
        console.print(f"[green]Unsubscribed[/green] {topic}")


@app.command()
def pause(subscription: str = typer.Argument(...)) -> None:
    """Pause a subscription."""
    _set_status(subscription, SubscriptionStatus.PAUSED, "Paused")


@app.command()
def resume(subscription: str = typer.Argument(...)) -> None:
    """Resume a paused subscription."""
    _set_status(subscription, SubscriptionStatus.ACTIVE, "Resumed")


def _set_status(prefix: str, status: SubscriptionStatus, verb: str) -> None:
    with session_scope() as session:
        sub = subscription_repo.get_by_prefix(session, prefix)
        if sub is None:
            _fail(f"No single subscription matches {prefix!r}.")
            return
        subscription_repo.set_status(session, sub, status)
        console.print(f"[green]{verb}[/green] {sub.topic}")


def _render(delivery: Delivery) -> None:
    console.print()
    console.print(f"[bold]{delivery.title}[/bold]")
    console.print(
        f"[dim]{delivery.subscription.topic} · issue {delivery.issue_number} · "
        f"depth {delivery.depth} · {delivery.duration_minutes}min read[/dim]\n"
    )
    console.print(Markdown(delivery.body_markdown))
    console.print(f"\n[dim]{_short(delivery.id)} · halflife feedback {_short(delivery.id)} too-basic|just-right|too-advanced[/dim]")


if __name__ == "__main__":  # pragma: no cover
    app()
