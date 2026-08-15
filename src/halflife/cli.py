"""The step-1 surface: one person, one machine, reading their own subscriptions.

Everything here goes through repositories and the engine, so that the MCP server
(step 2) and the API (step 3) are new front doors on the same code.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from halflife.db import session_scope
from halflife.generation import GenerationError, engine
from halflife.migrations_runner import upgrade_to_head
from halflife.models.base import Feedback, SubscriptionStatus, utcnow
from halflife.models.delivery import Delivery
from halflife.repository import deliveries as delivery_repo
from halflife.repository import series as series_repo
from halflife.repository import subscriptions as subscription_repo
from halflife.shorthand import ShorthandError, parse_shorthand

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
}


def _short(identifier: str) -> str:
    return identifier[:8]


def _fail(message: str) -> None:
    console.print(f"[red]{message}[/red]")
    raise typer.Exit(code=1)


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
        if plan:
            with console.status("Planning the series arc..."):
                try:
                    series = engine.plan_series(session=session, subscription=subscription)
                except GenerationError as exc:
                    _fail(f"Could not plan the series: {exc}")
                    return
            console.print(f"\n[dim]{series.arc_summary}[/dim]\n")
            for entry in series.plan:
                console.print(f"  {entry['index']:>2}. {entry['title']}")


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
                str(series.issue_count if series else 0),
                sub.next_due_at.strftime("%Y-%m-%d %H:%M"),
                "" if sub.status is SubscriptionStatus.ACTIVE else "[dim]paused[/dim]",
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

        for sub in due:
            with console.status(f"Generating: {sub.topic}"):
                try:
                    delivery = engine.generate_next(session=session, subscription=sub)
                except GenerationError as exc:
                    console.print(f"[red]{sub.topic}: {exc}[/red]")
                    continue
            console.print(
                f"[green]#{delivery.issue_number}[/green] {delivery.title}  "
                f"[dim]{_short(delivery.id)}[/dim]"
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
    verdict: str = typer.Argument(..., help="too-basic | just-right | too-advanced"),
) -> None:
    """Record depth feedback. Too basic or too advanced nudges the subscription's depth."""
    parsed = _FEEDBACK_ALIASES.get(verdict.lower())
    if parsed is None:
        _fail("Verdict must be one of: too-basic, just-right, too-advanced.")
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
        if after == before:
            console.print(f"[green]Noted.[/green] Depth stays at {after}.")
        else:
            console.print(f"[green]Noted.[/green] Depth {before} -> {after} for future issues.")


@app.command()
def series(
    subscription: str = typer.Argument(..., help="Subscription id or prefix."),
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
        console.print(f"\n[bold]Coverage ledger[/bold] ({len(points)} points)")
        for point in points:
            console.print(f"  - {point.point}")

        console.print("\n[bold]Open threads[/bold]")
        if state.open_threads:
            for thread in state.open_threads:
                console.print(f"  - {thread}")
        else:
            console.print("  [dim]none[/dim]")


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
