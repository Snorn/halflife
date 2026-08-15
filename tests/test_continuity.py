from __future__ import annotations

from halflife.generation import continuity
from halflife.generation.continuity import MAX_LEDGER_POINTS
from halflife.models.base import new_id
from halflife.models.series import CoveragePoint, Series
from tests.conftest import make_issue


def _series(**kwargs) -> Series:
    defaults = dict(
        id=new_id(),
        tenant_id="local",
        subscription_id=new_id(),
        arc_summary="An arc.",
        plan=[],
        plan_prompt_version="1",
        open_threads=[],
        issue_count=0,
    )
    defaults.update(kwargs)
    return Series(**defaults)


def _points(series: Series, texts: list[str]) -> list[CoveragePoint]:
    return [
        CoveragePoint(
            id=new_id(),
            tenant_id="local",
            series_id=series.id,
            position=i,
            point=text,
        )
        for i, text in enumerate(texts)
    ]


def test_empty_ledger_says_so_rather_than_rendering_nothing():
    assert "first issue" in continuity.render_ledger_block([])


def test_ledger_block_carries_the_do_not_repeat_instruction():
    block = continuity.render_ledger_block(["a", "b"])
    assert "do NOT explain any of this again" in block
    assert "- a" in block and "- b" in block


def test_ledger_is_capped_and_says_when_it_elides():
    points = [f"point {i}" for i in range(MAX_LEDGER_POINTS + 5)]
    block = continuity.render_ledger_block(points)
    assert "5 oldest points are omitted" in block
    # The most recent points survive; the oldest do not.
    assert f"point {MAX_LEDGER_POINTS + 4}" in block
    assert "- point 0\n" not in block


def test_no_plan_tells_the_model_to_choose():
    assert "Choose the subject yourself" in continuity.render_plan_block([], "", 1)


def test_plan_block_marks_the_current_issue_and_what_is_written():
    plan = [
        {"index": 1, "title": "One", "focus": "f1"},
        {"index": 2, "title": "Two", "focus": "f2"},
        {"index": 3, "title": "Three", "focus": "f3"},
    ]
    lines = continuity.render_plan_block(plan, "An arc.", issue_number=2).splitlines()
    by_index = {n: next(line for line in lines if f" {n}. " in line) for n in (1, 2, 3)}

    assert "[already written]" in by_index[1]
    assert "->" in by_index[2]
    assert "[already written]" not in by_index[3]
    assert "Arc: An arc." in "\n".join(lines)


def test_threads_block_when_empty():
    assert continuity.render_threads_block([]) == "Open threads: none."


def test_apply_issue_appends_points_and_replaces_threads():
    series = _series()
    series.coverage.extend(_points(series, ["old"]))
    series.open_threads = ["stale thread"]

    issue = make_issue(2, points=["new one", "new two"], threads=["fresh thread"])
    added = continuity.apply_issue(
        series=series, issue=issue, delivery_id="d1", tenant_id="local"
    )

    assert [p.point for p in added] == ["new one", "new two"]
    # Coverage is append-only and positions continue from where they left off.
    assert [p.position for p in series.coverage] == [0, 1, 2]
    # Threads are replaced wholesale — a thread not carried forward is dropped.
    assert series.open_threads == ["fresh thread"]
    assert series.issue_count == 1


def test_apply_issue_drops_blank_points_and_threads():
    series = _series()
    issue = make_issue(1, points=["real", "  ", ""], threads=["  "])
    continuity.apply_issue(series=series, issue=issue, delivery_id="d1", tenant_id="local")
    assert [p.point for p in series.coverage] == ["real"]
    assert series.open_threads == []
