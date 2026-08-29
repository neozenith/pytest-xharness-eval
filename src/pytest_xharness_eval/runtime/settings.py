"""Where the plugin's configuration comes from -- for both of the paths that need it.

A sweep reads its settings from the live :class:`pytest.Config`. A replay runs outside
any pytest session and has to resolve the same keys from disk, the way pytest finds its
rootdir. Those were two implementations of one idea, and they drifted independently:
the ini key names, their defaults and the paths they resolve to are declared once here,
and both entry points build the same :class:`Settings` (ADR 0014, ADR 0026, ADR 0030).

Every location is an ini key resolved against the project root; nothing is derived from
``__file__`` except the bundled price table (ADR 0014).
"""

from __future__ import annotations

# Standard Library
import configparser
import tomllib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

# Our Libraries
from pytest_xharness_eval.derive import pricing
from pytest_xharness_eval.model import matrix as mx
from pytest_xharness_eval.model.layout import CacheLayout

if TYPE_CHECKING:
    # Standard Library
    from collections.abc import Iterator
    from pathlib import Path

    # Third Party
    import pytest

    # Our Libraries
    from pytest_xharness_eval.model.case import EvalCase

INI_SKILLS_DIR = "xharness_skills_dir"
INI_CACHE_DIR = "xharness_cache_dir"
INI_PRICES = "xharness_prices"
INI_MATRIX = "xharness_matrix"
INI_SKILL_IGNORE = "xharness_skill_ignore"
INI_REPORT_TOKENS = "xharness_report_design_tokens"
INI_REPORT_INLINE = "xharness_report_inline"

DEFAULT_SKILLS_DIR = "skills"
DEFAULT_CACHE_DIR = ".xharness_eval_cache"

# pytest's own config files, in the order it consults them (rootdir discovery).
_CONFIG_FILES = ("pytest.ini", ".pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg")


def _ini_options(path: Path) -> dict[str, Any] | None:
    """The pytest ini table in one config file, or ``None`` when the file is not pytest's.

    A ``pyproject.toml`` without ``[tool.pytest.ini_options]`` is not pytest's config
    file, so it does not stop the search -- which is how pytest itself decides.
    """
    if path.name == "pyproject.toml":
        section = tomllib.loads(path.read_text(encoding="utf-8")).get("tool", {}).get("pytest", {})
        options = section.get("ini_options")
        return dict(options) if isinstance(options, dict) else None
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path, encoding="utf-8")
    name = "tool:pytest" if path.name == "setup.cfg" else "pytest"
    return dict(parser[name]) if parser.has_section(name) else None


def _discover(start: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Yield the one (directory, ini table) that governs ``start``, the way pytest finds it."""
    for directory in (start.resolve(), *start.resolve().parents):
        for name in _CONFIG_FILES:
            path = directory / name
            if not path.is_file():
                continue
            options = _ini_options(path)
            if options is not None:
                yield directory, options
                return


def find_rootpath(start: Path) -> Path:
    """The directory whose pytest config governs ``start``; ``start`` itself when none is found."""
    for directory, _options in _discover(start):
        return directory
    return start.resolve()


def ini_value(start: Path, key: str) -> Any:
    """The raw pytest ini value for ``key`` as read from disk; ``None`` when unset."""
    for _directory, options in _discover(start):
        return options.get(key)
    return None


def ini_lines(start: Path, key: str) -> list[str]:
    """A linelist ini key's lines, read from disk; a missing file or key is no lines."""
    value = ini_value(start, key)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [line.strip() for line in str(value).splitlines() if line.strip()]


@dataclass(frozen=True)
class Settings:
    """One resolved view of a project's configuration, however it was read."""

    rootpath: Path
    skills_root: Path
    # The cache tree, not the bare path to it: every location under it has one owner
    # (ADR 0037), so no caller reassembles ``<cache>/results`` or ``<cache>/build``.
    cache: CacheLayout
    price_lines: list[str] = field(default_factory=list)
    matrix_lines: list[str] = field(default_factory=list)
    skill_ignore: list[str] = field(default_factory=list)
    report_tokens: Path | None = None
    report_inline: bool = False

    # -- constructors ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: pytest.Config) -> Settings:
        """The live-sweep view: every key read off the pytest session that is running."""
        tokens = config.getoption("xharness_report_design_tokens", None) or str(config.getini(INI_REPORT_TOKENS))
        return cls(
            rootpath=config.rootpath,
            skills_root=(config.rootpath / str(config.getini(INI_SKILLS_DIR))).resolve(),
            cache=CacheLayout(config.rootpath / str(config.getini(INI_CACHE_DIR))),
            price_lines=[str(line) for line in config.getini(INI_PRICES)],
            matrix_lines=[str(e).strip() for e in config.getini(INI_MATRIX) if str(e).strip()],
            skill_ignore=[str(p) for p in config.getini(INI_SKILL_IGNORE)],
            report_tokens=(config.rootpath / tokens) if tokens else None,
            report_inline=bool(config.getoption("xharness_report_inline", False) or config.getini(INI_REPORT_INLINE)),
        )

    @classmethod
    def from_cache(
        cls,
        cache: Path,
        *,
        prices: list[str] | None = None,
        ignore: list[str] | None = None,
        report_tokens: Path | None = None,
        report_inline: bool = False,
    ) -> Settings:
        """The replay view: the same keys resolved from the project owning ``cache``.

        ``cache`` is where the caller pointed the rebuild, so it is taken as given rather
        than re-read; ``prices`` and ``ignore`` add to the project's own lines, in the
        same ini-line forms, so a replay can try a rate or an exclusion without editing
        the project's config.
        """
        rootpath = find_rootpath(cache)
        return cls(
            rootpath=rootpath,
            skills_root=rootpath / str(ini_value(cache, INI_SKILLS_DIR) or DEFAULT_SKILLS_DIR),
            cache=CacheLayout(cache),
            price_lines=ini_lines(cache, INI_PRICES) + list(prices or []),
            matrix_lines=ini_lines(cache, INI_MATRIX),
            skill_ignore=ini_lines(cache, INI_SKILL_IGNORE) + list(ignore or []),
            report_tokens=report_tokens,
            report_inline=report_inline,
        )

    # -- derived views -----------------------------------------------------------------

    def price_table(self) -> dict[str, pricing.Rates]:
        """The bundled table with this project's rows layered on top (ADR 0030)."""
        return pricing.load_table(rows=self.price_lines)

    def matrix_for(self, case: EvalCase) -> list[str]:
        """Case > project ini > plugin default (ADR 0015)."""
        return case.models or self.matrix_lines or list(mx.DEFAULT_MATRIX)

    def skill_dir(self, skill: str) -> Path:
        """Where the skill under test lives."""
        return self.skills_root / skill
