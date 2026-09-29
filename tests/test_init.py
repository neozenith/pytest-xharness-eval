"""The package root: its version and its public names."""

# Standard Library
import tomllib

# Third Party
import pytest

# Our Libraries
from pytest_xharness_eval import (
    __version__,
)


def test_version_matches_pyproject(pytestconfig: pytest.Config) -> None:
    """`version` in pyproject.toml and `__version__` are declared twice; a release bumps both (ADR 0017)."""
    pyproject = tomllib.loads((pytestconfig.rootpath / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == pyproject["project"]["version"]
