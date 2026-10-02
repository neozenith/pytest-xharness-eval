"""``model.layout``: every path under the cache root, and the run stamp's day (ADR 0037, ADR 0050)."""

# Standard Library
from datetime import date
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.model.layout import CacheLayout, SessionDir, model_level, run_date, split_model_level


@pytest.mark.parametrize(
    ("model", "rung", "treatment", "level"),
    [
        ("claude-opus-5", "high", None, "claude-opus-5--high"),
        ("claude-opus-5", None, None, "claude-opus-5"),
        ("claude-opus-5", "high", "lean-ci", "claude-opus-5--high+lean-ci"),
        ("gpt-5.6-luna", None, "lean-ci", "gpt-5.6-luna+lean-ci"),
    ],
)
def test_effort_and_treatment_ride_the_model_level_and_split_back_off_it(
    model: str, rung: str | None, treatment: str | None, level: str
) -> None:
    """The evidence tree stays five levels deep, so the page's fetch contract is unchanged (ADR 0049, ADR 0055)."""
    assert model_level(model, rung, treatment) == level
    assert split_model_level(level) == (model, rung, treatment)


def test_a_session_directory_carries_the_rung_without_gaining_a_level(tmp_path: Path) -> None:
    cache = CacheLayout(tmp_path)
    located = cache.session(
        skill="demo", harness="claude", model="opus", effort="high", run="20260101T000000Z", session="sid"
    )
    assert located.rel == "demo/claude/opus--high/20260101T000000Z/sid"
    assert located.report_link("log.jsonl") == "../results/demo/claude/opus--high/20260101T000000Z/sid/log.jsonl"
    located.mkdir()
    # The walk reads the coordinates back off the tree, rung included, and a level written
    # before ADR 0049 still reads as "named no effort" rather than failing to parse.
    plain = cache.session(skill="demo", harness="codex", model="sol", run="20260101T000000Z", session="sid2")
    plain.mkdir()
    walked = {(s.model, s.effort) for s in cache.sessions()}
    assert walked == {("opus", "high"), ("sol", None)}


def test_a_session_directory_carries_the_treatment_without_gaining_a_level(tmp_path: Path) -> None:
    cache = CacheLayout(tmp_path)
    located = cache.session(
        skill="demo", harness="codex", model="luna", treatment="lean-ci", run="20260101T000000Z", session="sid"
    )
    assert located.rel == "demo/codex/luna+lean-ci/20260101T000000Z/sid"
    located.mkdir()
    # A level written before ADR 0055 reads back as the control, not as a parse failure.
    cache.session(skill="demo", harness="codex", model="luna", run="20260101T000000Z", session="sid2").mkdir()
    assert {(s.model, s.treatment) for s in cache.sessions()} == {("luna", "lean-ci"), ("luna", None)}


def test_a_run_stamp_names_the_day_it_is_priced_on() -> None:
    assert run_date("20260928T101500Z") == date(2026, 9, 28)
    # The all-zero stamp a legacy migration writes for an undatable capture names no day.
    assert run_date("00000000T000000Z") is None
    located = CacheLayout(Path("/c")).session(
        skill="s", harness="claude", model="m", run="20260101T000000Z", session="x"
    )
    assert located.run_date == date(2026, 1, 1)


def test_cache_layout_names_every_path_in_the_tree(tmp_path: Path) -> None:
    """Each name is declared once; nothing else reassembles one of these paths."""
    cache = CacheLayout(tmp_path / "cache")
    assert (cache.build, cache.results, cache.report) == (
        tmp_path / "cache" / "build",
        tmp_path / "cache" / "results",
        tmp_path / "cache" / "report",
    )
    assert [p.name for p in (cache.index, cache.history, cache.summary, cache.page, cache.tokens, cache.glossary)] == [
        "index.json",
        "history.jsonl",
        "report.json",
        "report.html",
        "report.tokens.json",
        "XHARNESS-REPORT-GLOSSARY.md",
    ]
    session = cache.session(skill="demo", harness="claude", model="opus", run="20261022T000000Z", session="sid1")
    assert session.path == cache.results / "demo" / "claude" / "opus" / "20261022T000000Z" / "sid1"
    assert session.rel == "demo/claude/opus/20261022T000000Z/sid1"
    assert [p.name for p in (session.log, session.result, session.history, session.subagents)] == [
        "log.jsonl",
        "result.json",
        "history.json",
        "subagents",
    ]
    # The page fetches its evidence relative to report/, where index.json sits (ADR 0032).
    assert session.report_link("log.jsonl") == "../results/demo/claude/opus/20261022T000000Z/sid1/log.jsonl"


def test_cache_layout_walks_the_five_levels_and_keeps_the_coordinates(tmp_path: Path) -> None:
    """The walk the index, the aggregated history and the replay all share."""
    cache = CacheLayout(tmp_path / "cache")
    for model in ("sonnet", "opus"):
        cache.session(skill="demo", harness="claude", model=model, run="20261022T000000Z", session="sid").mkdir()
    # Neither a file at the session level nor a directory at the wrong depth is a session.
    (cache.results / "demo" / "claude" / "opus" / "20261022T000000Z" / "stray.txt").write_text("x", encoding="utf-8")
    (cache.results / "demo" / "shallow").mkdir(parents=True)

    found = list(cache.sessions())
    assert [(s.model, s.session) for s in found] == [("opus", "sid"), ("sonnet", "sid")]
    assert {(s.skill, s.harness, s.run) for s in found} == {("demo", "claude", "20261022T000000Z")}
    # A cache with no results/ at all walks to nothing rather than raising.
    assert list(CacheLayout(tmp_path / "empty").sessions()) == []


def test_a_session_dir_addressed_by_path_cannot_publish_a_report_link(tmp_path: Path) -> None:
    """The two variants are two types, so a garbage key is unrepresentable (ADR 0038).

    A caller handed a directory -- a replay, a harness adapter re-reading its own captured
    log -- gets the four documents and ``mkdir()``. It does not get ``rel`` or a report
    link, because a bare path does not know where it sits in a cache: when one type served
    both jobs with the coordinates defaulting to empty, that caller published ``"////sid1"``
    as a session key and no one was told.
    """
    session = SessionDir(tmp_path / "sid1")
    assert session.session == "sid1"
    assert session.log == tmp_path / "sid1" / "log.jsonl"
    assert session.mkdir().is_dir()
    assert not hasattr(session, "rel") and not hasattr(session, "report_link")

    located = CacheLayout(tmp_path).session(skill="s", harness="h", model="m", run="r", session="sid1")
    assert isinstance(located, SessionDir) and located.rel == "s/h/m/r/sid1"
