"""``runtime.settings``: resolving ini keys for a sweep and a replay (ADR 0034)."""

# Standard Library
from pathlib import Path

# Third Party
import pytest

# Our Libraries
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
