"""Report the G1 daily-use gate against the live database.

Run it rather than working the number out by hand:

    .venv/Scripts/python scripts/gate.py

The gate asks whether HalfLife is opened on a day when nothing is being built
for it. That is why the read-only line exists and why it is the one to look at:
a day that also generated something is a day the maintainer was working on the
tool, which is exactly the case the gate is trying to exclude.

Days are counted in the machine's local timezone. Counting them in UTC, which
is how they are stored, under-reported the gate by a day for as long as it was
measured by hand — see tests/test_usage_days.py.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from halflife.db import session_scope  # noqa: E402
from halflife.repository import deliveries as delivery_repo  # noqa: E402

# Redirected output falls back to the ANSI code page, which cannot represent the
# punctuation this prints. Same reason the CLI does it; see cli._force_utf8.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

TARGET_DAYS = 7


def _run(days: set[date]) -> int:
    """Length of the longest run of consecutive days, or 0 if there are none."""
    if not days:
        return 0
    ordered = sorted(days)
    best = run = 1
    for earlier, later in zip(ordered, ordered[1:]):
        run = run + 1 if later - earlier == timedelta(days=1) else 1
        best = max(best, run)
    return best


def main() -> int:
    with session_scope() as session:
        usage = delivery_repo.usage_days(session)

    any_use = usage.any_use
    print(f"G1 — usable daily for a week ({TARGET_DAYS} days)\n")
    print(f"  days with any use   {len(any_use):>2}   {', '.join(str(d) for d in sorted(any_use))}")
    print(f"  longest run         {_run(any_use):>2}")
    print(f"  written             {len(usage.written):>2}")
    print(f"  fetched             {len(usage.fetched):>2}")
    print(f"  rated               {len(usage.rated):>2}")

    read_only = usage.read_only
    print(
        f"\n  read but not built  {len(read_only):>2}"
        f"   {', '.join(str(d) for d in sorted(read_only)) or '—'}"
    )
    print("  " + "-" * 60)
    if len(read_only) >= TARGET_DAYS:
        print("  MET — used on days nothing was being built for it.")
        return 0
    print(
        f"  NOT MET — {TARGET_DAYS - len(read_only)} more day(s) of reading without\n"
        "  generating would answer the question the gate actually asks."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
