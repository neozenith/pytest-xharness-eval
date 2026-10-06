"""``runtime.settings``: resolving ini keys for a sweep and a replay (ADR 0034)."""

# Standard Library
from datetime import date
from pathlib import Path

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval.model.case import evalcase
from pytest_xharness_eval.model.layout import CacheLayout
from pytest_xharness_eval.runtime import settings


@pytest.mark.parametrize(
    ("name", "body"),
    [
        (
            "pyproject.toml",
            '[tool.pytest.ini_options]\nxharness_skill_ignore = ["README.md", "demo: assets/"]\n',
        ),
        ("pytest.ini", "[pytest]\nxharness_skill_ignore =\n    README.md\n    demo: assets/\n"),
        ("tox.ini", "[pytest]\nxharness_skill_ignore =\n    README.md\n    demo: assets/\n"),
        ("setup.cfg", "[tool:pytest]\nxharness_skill_ignore =\n    README.md\n    demo: assets/\n"),
    ],
)
def test_settings_read_skill_ignore_from_the_projects_pytest_config(tmp_path: Path, name: str, body: str) -> None:
    captured = tmp_path / "skills" / "demo" / "evals" / "captured"
    captured.mkdir(parents=True)
    (tmp_path / name).write_text(body, encoding="utf-8")
    assert settings.ini_lines(captured, "xharness_skill_ignore") == ["README.md", "demo: assets/"]


def test_settings_ignore_a_pyproject_without_pytest_options_and_a_missing_config(tmp_path: Path) -> None:
    captured = tmp_path / "skills" / "demo" / "evals" / "captured"
    captured.mkdir(parents=True)
    assert settings.ini_lines(captured, "xharness_skill_ignore") == []
    (tmp_path / "skills" / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nxharness_skill_ignore = ["assets/"]\n', encoding="utf-8"
    )
    assert settings.ini_lines(captured, "xharness_skill_ignore") == [
        "assets/"
    ]  # the nearer pyproject is not pytest's config file


def test_treatments_resolve_case_then_project_then_none(tmp_path: Path) -> None:
    """Unlike the matrix, the plugin default is empty: a treatment is a directory a project writes (ADR 0055)."""

    def grader(output: object) -> None:
        pass

    plain = evalcase(task="t", skill="s", fixture="f")(grader)
    treated = evalcase(task="t", skill="s", fixture="f", treatments=["terse"])(grader)
    bare = settings.Settings(rootpath=tmp_path, skills_root=tmp_path, cache=CacheLayout(tmp_path))
    project = settings.Settings(
        rootpath=tmp_path, skills_root=tmp_path, cache=CacheLayout(tmp_path), treatment_lines=["lean-ci"]
    )
    assert bare.treatments_for(plain) == []
    assert project.treatments_for(plain) == ["lean-ci"]
    assert project.treatments_for(treated) == ["terse"]


def test_a_replay_reads_the_projects_treatment_lines(tmp_path: Path) -> None:
    cache = tmp_path / ".xharness_eval_cache"
    cache.mkdir()
    (tmp_path / "pytest.ini").write_text("[pytest]\nxharness_treatments =\n    lean-ci\n", encoding="utf-8")
    assert settings.Settings.from_cache(cache).treatment_lines == ["lean-ci"]


def test_ensure_priced_fetches_nothing_when_every_entry_is_priced(tmp_path: Path) -> None:
    """A sweep of priced models never touches the feed: here it points at a file that does not exist."""
    s = settings.Settings(
        rootpath=tmp_path, skills_root=tmp_path, cache=CacheLayout(tmp_path / "cache"), price_feed=str(tmp_path / "x")
    )
    s.ensure_priced(["codex/gpt-5.6-sol"], date(2026, 10, 7)).validate_matrix(["codex/gpt-5.6-sol"], date(2026, 10, 7))
    assert not (tmp_path / "cache" / "pricing").exists()


def test_ensure_priced_saves_a_gap_it_finds_in_the_feed_as_a_cache_record(tmp_path: Path) -> None:
    """The record is read back by every later settings view, so a replay prices the run the same way (ADR 0060)."""
    source = tmp_path / "feed.json"
    entry = '{"litellm_provider": "openai", "input_cost_per_token": 2e-06, "output_cost_per_token": 1.2e-05}'
    source.write_text(f'{{"gpt-7-terra": {entry}}}', encoding="utf-8")
    s = settings.Settings(
        rootpath=tmp_path, skills_root=tmp_path, cache=CacheLayout(tmp_path / "cache"), price_feed=str(source)
    )
    day = date(2026, 10, 7)
    s.ensure_priced(["codex/gpt-7-terra", "codex/gpt-7-sol"], day)
    assert (tmp_path / "cache" / "pricing" / "prices-20261007.toml").is_file()
    assert s.price_table().unpriced(["codex/gpt-7-terra", "codex/gpt-7-sol"], day) == [("codex", "gpt-7-sol")]
